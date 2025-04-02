import os
import json
import random
import string
import time
import threading
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from bip44 import Wallet as Bip44Wallet
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
from decimal import Decimal
from models import Wallet, Transaction, db
from datetime import datetime

# Load environment variables
load_dotenv()

# Binance Smart Chain settings
BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/')
USDT_CONTRACT_ADDRESS = os.getenv('USDT_CONTRACT_ADDRESS', '0x55d398326f99059fF775485246999027B3197955')  # BEP20 USDT
USDT_ABI = json.loads(os.getenv('USDT_ABI', '''[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]'''))

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
# For newer web3 versions, middleware is handled differently
# We can connect to BSC without explicit middleware

# USDT token contract
usdt_contract = w3.eth.contract(address=Web3.to_checksum_address(USDT_CONTRACT_ADDRESS), abi=USDT_ABI)

# Web3 configuration for BEP-20 USDT (Binance Smart Chain)
BLOCKCHAIN_PROVIDER = os.environ.get('BLOCKCHAIN_PROVIDER', 'https://bsc-dataseed.binance.org/')
WEB3_PROVIDER = Web3(Web3.HTTPProvider(BLOCKCHAIN_PROVIDER))
CHAIN_ID = 56  # Binance Smart Chain Mainnet (Use 97 for testnet)

# Platform admin wallet for fees and escrow
PLATFORM_WALLET_ADDRESS = "0x1234567890123456789012345678901234567890"  # CHANGE THIS TO YOUR PLATFORM WALLET
PLATFORM_PRIVATE_KEY = os.environ.get("PLATFORM_PRIVATE_KEY", "")  # Get this from environment variable

# Gas settings
GAS_LIMIT = 100000
GAS_PRICE = WEB3_PROVIDER.to_wei('5', 'gwei')  # Adjust based on network conditions

class WalletService:
    def __init__(self, app):
        self.app = app
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
    def _get_or_create_encryption_key(self):
        """Get encryption key from environment or create and store a new one."""
        key = os.getenv('WALLET_ENCRYPTION_KEY')
        if not key:
            # Generate a secure key
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            # In production, this should be stored securely, not as an env var
            os.environ['WALLET_ENCRYPTION_KEY'] = key.decode()
            with open('.env', 'a') as f:
                f.write(f'\nWALLET_ENCRYPTION_KEY={key.decode()}')
        else:
            key = key.encode()
        return key
    
    def create_wallet(self):
        """Create a new BEP20 wallet."""
        # Generate a mnemonic (seed phrase)
        # For production, consider using a more secure entropy source
        account = Account.create()
        private_key = account.key.hex()
        public_address = account.address
        
        # Encrypt the private key before storing
        encrypted_key = self.encrypt_private_key(private_key)
        
        return {
            'address': public_address,
            'encrypted_private_key': encrypted_key
        }
    
    def encrypt_private_key(self, private_key):
        """Encrypt a private key using Fernet symmetric encryption."""
        return self.fernet.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted_key):
        """Decrypt an encrypted private key."""
        return self.fernet.decrypt(encrypted_key.encode()).decode()
    
    def get_usdt_balance(self, address):
        """Get USDT balance for a wallet address."""
        try:
            balance = usdt_contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
            # USDT has 18 decimals on BSC
            return str(balance / 10**18)
        except Exception as e:
            print(f"Error getting balance: {e}")
            return "0"
    
    def send_usdt(self, from_address, to_address, amount, private_key):
        """Send USDT from one address to another."""
        try:
            # Convert to checksum addresses
            from_address = Web3.to_checksum_address(from_address)
            to_address = Web3.to_checksum_address(to_address)
            
            # Convert amount to wei (18 decimals for USDT on BSC)
            amount_wei = int(float(amount) * 10**18)
            
            # Build the transaction
            nonce = w3.eth.get_transaction_count(from_address)
            gas_price = w3.eth.gas_price
            
            # Estimate gas for the transaction
            transaction = usdt_contract.functions.transfer(
                to_address, 
                amount_wei
            ).build_transaction({
                'chainId': 56,  # BSC mainnet
                'gas': 100000,  # Estimated gas limit
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            
            # Sign the transaction
            signed_transaction = w3.eth.account.sign_transaction(transaction, private_key)
            
            # Send the transaction - Handle both old and new Web3.py versions
            try:
                # For newer Web3.py versions
                tx_hash = w3.eth.send_raw_transaction(signed_transaction.raw_transaction)
            except AttributeError:
                # Fall back to older Web3.py version format
                tx_hash = w3.eth.send_raw_transaction(signed_transaction.rawTransaction)
            
            return {
                'status': 'pending',
                'tx_hash': tx_hash.hex()
            }
        except Exception as e:
            print(f"Error sending USDT: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def check_transaction_status(self, tx_hash):
        """Check the status of a transaction."""
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return {'status': 'pending'}
            
            status = 'completed' if receipt.status == 1 else 'failed'
            block_number = receipt.blockNumber
            
            return {
                'status': status,
                'block_number': block_number
            }
        except Exception as e:
            print(f"Error checking transaction status: {e}")
            return {'status': 'unknown', 'error': str(e)}

def is_connected():
    """Check if connected to blockchain network"""
    return WEB3_PROVIDER.is_connected()

def get_wallet_balance(address):
    """Get real USDT balance from blockchain"""
    if not WEB3_PROVIDER.is_address(address):
        return Decimal('0')
    
    try:
        balance_wei = usdt_contract.functions.balanceOf(address).call()
        decimals = usdt_contract.functions.decimals().call()
        balance = Decimal(balance_wei) / Decimal(10 ** decimals)
        return balance
    except Exception as e:
        print(f"Error getting balance for {address}: {e}")
        return Decimal('0')

def update_wallet_balance(wallet_id):
    """Update database wallet balance with actual blockchain balance"""
    with db.app.app_context():
        wallet = Wallet.query.get(wallet_id)
        if wallet and wallet.address:
            real_balance = get_wallet_balance(wallet.address)
            wallet.balance = str(real_balance)
            db.session.commit()
            return real_balance
        return None

def send_usdt(from_address, to_address, amount, private_key):
    """Send USDT from one address to another using private key"""
    if not WEB3_PROVIDER.is_connected():
        raise Exception("Not connected to blockchain network")
    
    if not WEB3_PROVIDER.is_address(from_address) or not WEB3_PROVIDER.is_address(to_address):
        raise Exception("Invalid wallet addresses")
    
    try:
        # Convert amount to wei (consider USDT decimals)
        decimals = usdt_contract.functions.decimals().call()
        amount_wei = int(Decimal(amount) * Decimal(10 ** decimals))
        
        # Check sender balance
        balance = usdt_contract.functions.balanceOf(from_address).call()
        if balance < amount_wei:
            raise Exception("Insufficient balance for transfer")
            
        # Create transaction
        nonce = WEB3_PROVIDER.eth.get_transaction_count(from_address)
        
        # Build transaction for token transfer
        txn = usdt_contract.functions.transfer(
            to_address, 
            amount_wei
        ).build_transaction({
            'chainId': CHAIN_ID,
            'gas': GAS_LIMIT,
            'gasPrice': GAS_PRICE,
            'nonce': nonce,
        })
        
        # Sign transaction
        signed_txn = WEB3_PROVIDER.eth.account.sign_transaction(txn, private_key)
        
        # Send transaction
        tx_hash = WEB3_PROVIDER.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Wait for transaction receipt
        tx_receipt = WEB3_PROVIDER.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if tx_receipt.status == 1:
            # Transaction successful
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'block_number': tx_receipt.blockNumber
            }
        else:
            raise Exception("Transaction failed")
            
    except Exception as e:
        raise Exception(f"Error sending USDT: {str(e)}")

def complete_order_blockchain(order, buyer_wallet, seller_wallet):
    """
    Execute actual blockchain transfer for an order
    
    This function should be called when both parties confirm an order
    It transfers the agreed amount from buyer to seller
    """
    from app import get_app_config
    
    # Get amount from order
    try:
        # Parse the amount from order post description
        if "USDT Quantity:" in order.post.description:
            quantity_text = order.post.description.split("USDT Quantity:")[1].split(",")[0].strip()
            amount = Decimal(quantity_text)
        else:
            amount = Decimal('1.0')  # Default fallback
        
        # Add platform fee (e.g., 1%)
        platform_fee = amount * Decimal('0.01')
        
        # First transfer platform fee to platform wallet
        if get_app_config('USE_REAL_BLOCKCHAIN') == 'True':
            # Get buyer's private key (this would be securely stored/retrieved in production)
            # For demo, we'd use an environment variable or secure storage
            buyer_private_key = os.environ.get(f"WALLET_KEY_{buyer_wallet.id}", "")
            
            if not buyer_private_key:
                raise Exception("Buyer private key not available")
            
            # Transfer fee to platform
            fee_result = send_usdt(
                buyer_wallet.address,
                PLATFORM_WALLET_ADDRESS,
                str(platform_fee),
                buyer_private_key
            )
            
            # Transfer main amount to seller
            transfer_result = send_usdt(
                buyer_wallet.address,
                seller_wallet.address,
                str(amount - platform_fee),
                buyer_private_key
            )
            
            # Record transactions in database
            with db.app.app_context():
                # Record fee transaction
                fee_tx = Transaction(
                    wallet_id=buyer_wallet.id,
                    tx_hash=fee_result['tx_hash'],
                    amount=str(platform_fee),
                    tx_type="fee",
                    status="completed",
                    to_address=PLATFORM_WALLET_ADDRESS,
                    block_number=fee_result['block_number']
                )
                db.session.add(fee_tx)
                
                # Record main transaction to seller
                seller_amount = amount - platform_fee
                main_tx = Transaction(
                    wallet_id=buyer_wallet.id,
                    tx_hash=transfer_result['tx_hash'],
                    amount=str(seller_amount),
                    tx_type="send",
                    status="completed",
                    to_address=seller_wallet.address,
                    block_number=transfer_result['block_number']
                )
                db.session.add(main_tx)
                
                # Record receipt transaction for seller
                receive_tx = Transaction(
                    wallet_id=seller_wallet.id,
                    tx_hash=transfer_result['tx_hash'],
                    amount=str(seller_amount),
                    tx_type="receive",
                    status="completed",
                    from_address=buyer_wallet.address,
                    block_number=transfer_result['block_number']
                )
                db.session.add(receive_tx)
                
                # Update wallet balances from blockchain
                update_wallet_balance(buyer_wallet.id)
                update_wallet_balance(seller_wallet.id)
                
                db.session.commit()
            
            return {
                'success': True,
                'tx_hash': transfer_result['tx_hash'],
                'fee_tx_hash': fee_result['tx_hash']
            }
        else:
            # Simulated transaction in demo mode
            # Just update database balances
            with db.app.app_context():
                # Deduct from buyer
                buyer_wallet.balance = str(Decimal(buyer_wallet.balance) - amount)
                
                # Add to seller
                seller_wallet.balance = str(Decimal(seller_wallet.balance) + amount)
                
                # Create transaction records
                tx_hash = f"simulated-{order.id}-{datetime.utcnow().timestamp()}"
                
                # Create transaction record
                transaction = Transaction(
                    wallet_id=buyer_wallet.id,
                    tx_hash=f"{tx_hash}-send",
                    amount=str(amount),
                    tx_type="send",
                    status="completed",
                    to_address=seller_wallet.address
                )
                db.session.add(transaction)
                
                # Create corresponding transaction for seller
                seller_transaction = Transaction(
                    wallet_id=seller_wallet.id,
                    tx_hash=f"{tx_hash}-receive",
                    amount=str(amount),
                    tx_type="receive",
                    status="completed",
                    from_address=buyer_wallet.address
                )
                db.session.add(seller_transaction)
                
                db.session.commit()
            
            return {
                'success': True,
                'tx_hash': tx_hash,
                'simulated': True
            }
    except Exception as e:
        raise Exception(f"Error completing order on blockchain: {str(e)}")

# Wallet monitoring thread
stop_monitoring_flag = threading.Event()

def monitor_wallets():
    """Periodically check and update wallet balances from blockchain"""
    while not stop_monitoring_flag.is_set():
        try:
            with db.app.app_context():
                wallets = Wallet.query.all()
                for wallet in wallets:
                    if wallet.address:
                        update_wallet_balance(wallet.id)
        except Exception as e:
            print(f"Error in wallet monitoring: {str(e)}")
        
        # Check every 60 seconds
        time.sleep(60)

monitoring_thread = None

def start_monitoring():
    """Start the wallet monitoring thread"""
    global monitoring_thread
    if monitoring_thread is None or not monitoring_thread.is_alive():
        stop_monitoring_flag.clear()
        monitoring_thread = threading.Thread(target=monitor_wallets)
        monitoring_thread.daemon = True
        monitoring_thread.start()
        print("Wallet monitoring started")

def stop_monitoring():
    """Stop the wallet monitoring thread"""
    stop_monitoring_flag.set()
    if monitoring_thread and monitoring_thread.is_alive():
        monitoring_thread.join(timeout=2.0)
        print("Wallet monitoring stopped") 