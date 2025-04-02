import os
import json
import random
import string
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from bip44 import Wallet as Bip44Wallet
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

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