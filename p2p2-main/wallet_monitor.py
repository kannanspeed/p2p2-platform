import time
import threading
import os
from dotenv import load_dotenv
from web3 import Web3
import json
import sqlite3
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
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "from", "type": "address"},
            {"indexed": true, "name": "to", "type": "address"},
            {"indexed": false, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]'''))

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
# For newer web3 versions, middleware is handled differently
# We can connect to BSC without explicit middleware

# USDT token contract
usdt_contract = w3.eth.contract(address=Web3.to_checksum_address(USDT_CONTRACT_ADDRESS), abi=USDT_ABI)

# Database connection
def get_db_connection():
    conn = sqlite3.connect('instance/peer.db')
    conn.row_factory = sqlite3.Row
    return conn

class WalletMonitor:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_block = 0
    
    def start(self):
        """Start the wallet monitoring service."""
        if self.running:
            print("Wallet monitoring service is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitoring_loop)
        self.thread.daemon = True
        self.thread.start()
        print("Wallet monitoring service started")
    
    def stop(self):
        """Stop the wallet monitoring service."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Wallet monitoring service stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop that checks for new transfers."""
        # Get the latest block number to start from
        self.last_block = w3.eth.block_number
        print(f"Starting monitoring from block {self.last_block}")
        
        while self.running:
            try:
                # Get the current block number
                current_block = w3.eth.block_number
                
                if current_block > self.last_block:
                    print(f"Checking blocks {self.last_block} to {current_block}")
                    
                    # Create a filter for Transfer events
                    transfer_filter = usdt_contract.events.Transfer.create_filter(
                        fromBlock=self.last_block + 1,
                        toBlock=current_block
                    )
                    
                    # Get all transfer events
                    events = transfer_filter.get_all_entries()
                    
                    if events:
                        print(f"Found {len(events)} transfer events")
                        self._process_events(events)
                    
                    # Update the last processed block
                    self.last_block = current_block
                
                # Sleep to avoid overloading the RPC endpoint
                time.sleep(15)  # Check every 15 seconds
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait longer on error
    
    def _process_events(self, events):
        """Process transfer events and update the database."""
        # Get all wallet addresses from the database
        conn = get_db_connection()
        wallets = conn.execute('SELECT id, user_id, address FROM wallet').fetchall()
        wallet_addresses = {wallet['address'].lower(): wallet for wallet in wallets}
        
        for event in events:
            try:
                # Extract event data
                to_address = event['args']['to'].lower()
                from_address = event['args']['from'].lower()
                value = event['args']['value'] / 10**18  # Convert from wei to USDT (18 decimals)
                tx_hash = event['transactionHash'].hex()
                
                # Check if the recipient is one of our users
                if to_address in wallet_addresses:
                    wallet = wallet_addresses[to_address]
                    wallet_id = wallet['id']
                    
                    print(f"Received {value} USDT to wallet {wallet_id} (address: {to_address})")
                    
                    # Check if this transaction is already recorded
                    existing_tx = conn.execute(
                        'SELECT id FROM transaction WHERE tx_hash = ?', 
                        (tx_hash,)
                    ).fetchone()
                    
                    if not existing_tx:
                        # Record the transaction
                        conn.execute(
                            'INSERT INTO transaction (wallet_id, tx_hash, amount, tx_type, status, from_address, created_at, block_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                            (wallet_id, tx_hash, str(value), 'receive', 'completed', from_address, datetime.utcnow(), event['blockNumber'])
                        )
                        
                        # Update wallet balance (optional, as the app fetches the current balance when needed)
                        # This could be implemented if you want to keep a local cache of balances
                        
                        conn.commit()
                        print(f"Recorded transaction {tx_hash}")
            except Exception as e:
                print(f"Error processing event: {e}")
        
        conn.close()

# Singleton instance
monitor = WalletMonitor()

def start_monitoring():
    """Start the monitoring service."""
    monitor.start()

def stop_monitoring():
    """Stop the monitoring service."""
    monitor.stop()

if __name__ == "__main__":
    print("Starting wallet monitoring service...")
    start_monitoring()
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping wallet monitoring service...")
        stop_monitoring() 