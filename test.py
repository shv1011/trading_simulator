import sys
import json
import asyncio
import websockets
from numpy import array, std, sqrt, cumsum  # More specific imports
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton
)
from sklearn.linear_model import QuantileRegressor
from datetime import datetime
import qasync
import traceback

print("Starting script execution...")

window = None 

class OrderBook:
    def __init__(self):
        self.bids = []
        self.asks = []
        self.timestamp = None

    def update(self, data):
        print(f"Received order book data: {data}")
        timestamp_str = data['timestamp']
        print(f"Original timestamp string: {timestamp_str}") 
        if timestamp_str.endswith('Z'):
            timestamp_str_cleaned = timestamp_str[:-1] 
            print(f"Timestamp string after removing Z: {timestamp_str_cleaned}") 
        else:
            timestamp_str_cleaned = timestamp_str 
            print(f"Timestamp string (no Z removed): {timestamp_str_cleaned}") 

        try:
            self.timestamp = datetime.fromisoformat(timestamp_str_cleaned)
            print(f"Successfully parsed timestamp: {self.timestamp}")
        except ValueError as e:
            print(f"Failed to parse timestamp string '{timestamp_str_cleaned}': {e}")
            self.timestamp = None 

        self.bids = sorted([[float(p), float(v)] for p,v in data['bids']], reverse=True)
        self.asks = sorted([[float(p), float(v)] for p,v in data['asks']])
        print(f"Updated order book - Bids: {len(self.bids)}, Asks: {len(self.asks)}")  

class TradeSimulator(QWidget):
    def __init__(self):
        print("TradeSimulator init called.") 
        super().__init__()
        self.order_book = OrderBook()
        self.init_ui()
        self.websocket = None 
        self.websocket_task = None 

    def init_ui(self):
        # Input
        input_layout = QVBoxLayout()
        self.exchange = QComboBox()
        self.exchange.addItems(["OKX", "Binance", "Coinbase"])
        self.asset = QComboBox()
        self.asset.addItems(["BTC-USDT-SWAP", "ETH-USDT-SWAP", "XRP-USDT-SWAP"])
        self.quantity = QLineEdit("100")
        
        input_layout.addWidget(QLabel("Exchange:"))
        input_layout.addWidget(self.exchange)
        input_layout.addWidget(QLabel("Asset:"))
        input_layout.addWidget(self.asset)
        input_layout.addWidget(QLabel("Quantity (USD):"))
        input_layout.addWidget(self.quantity)

        # Add Input for Order Type
        self.order_type = QComboBox()
        self.order_type.addItems(["Market", "Limit"])  
        input_layout.addWidget(QLabel("Order Type:"))
        input_layout.addWidget(self.order_type)

        # Add Input for Volatility
        self.volatility = QLineEdit("0.01")  
        input_layout.addWidget(QLabel("Volatility:"))
        input_layout.addWidget(self.volatility)

        # Add Input for Fee Tier
        self.fee_tier = QComboBox()
        self.fee_tier.addItems(["Tier 1", "Tier 2", "Tier 3"])
        input_layout.addWidget(QLabel("Fee Tier:"))
        input_layout.addWidget(self.fee_tier)

        # Add an Update Button
        self.update_button = QPushButton("Update Metrics")
        input_layout.addWidget(self.update_button)

        # Output Panel
        output_layout = QVBoxLayout()
        self.slippage_label = QLabel("Slippage: -")
        self.fees_label = QLabel("Fees: -")
        self.impact_label = QLabel("Market Impact: -")
        self.net_cost_label = QLabel("Net Cost: -")
        self.maker_taker_label = QLabel("Maker/Taker Proportion: -")
        self.latency_label = QLabel("Internal Latency: -")

        output_layout.addWidget(self.slippage_label)
        output_layout.addWidget(self.fees_label)
        output_layout.addWidget(self.impact_label)
        output_layout.addWidget(self.net_cost_label)
        output_layout.addWidget(self.maker_taker_label)
        output_layout.addWidget(self.latency_label)

        # Main Layout
        main_layout = QHBoxLayout()
        main_layout.addLayout(input_layout)
        main_layout.addLayout(output_layout)
        self.setLayout(main_layout)
        self.setWindowTitle('Crypto Trade Simulator')
        self.update_button.clicked.connect(self.on_update_button_clicked)

        self.show()

    async def start_websocket_client(self, exchange="OKX", asset="BTC-USDT-SWAP"):
        print("start_websocket_client called.")  # Debug print at the start
        if self.websocket and self.websocket.open:
            print("Closing existing WebSocket connection...")
            await self.websocket.close()
            self.websocket = None
            print("Existing WebSocket connection closed.")

        websocket_urls = {
            ("OKX", "BTC-USDT-SWAP"): "wss://ws.gomarket-cpp.goquant.io/ws/l2-orderbook/okx/BTC-USDT-SWAP",
        }

        uri = websocket_urls.get((exchange, asset))
        if not uri:
            print(f"No WebSocket URL found for {exchange} - {asset}")
            return

        print(f"Attempting to connect to WebSocket: {uri}")
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=20, 
                ping_timeout=20   
            )
            print("WebSocket connected.")
            
            self.websocket_task = asyncio.create_task(self.receive_websocket_data())
            print("WebSocket data receiving task started.")

        except Exception as e:
            print(f"WebSocket connection error for {exchange} - {asset}: {e}")
            self.websocket = None
            self.websocket_task = None

    async def receive_websocket_data(self):
        if not self.websocket:
            print("Receive task started but no websocket connection available.")
            return

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    self.order_book.update(data)
                    self.update_metrics()      
                except Exception as e:
                    print(f"WebSocket data processing error: {e}")
        except websockets.exceptions.ConnectionClosedOK:
            print("WebSocket connection closed gracefully.")
        except Exception as e:
            print(f"WebSocket receiving loop error: {e}")
        finally:
            print("WebSocket data receiving task finished.")
            self.websocket = None
            self.websocket_task = None

    def calculate_slippage(self):
        quantity = float(self.quantity.text())
        print(f"Calculating slippage for quantity: {quantity}")  
        volumes = array([v for p,v in self.order_book.asks]).cumsum()
        prices = [p for p,v in self.order_book.asks]
        print(f"Available volumes: {volumes}, prices: {prices}") 
        if len(prices) < 10:
            print("Not enough price data for slippage calculation")  
            return 0.0
        model = QuantileRegressor(quantile=0.95).fit(volumes.reshape(-1,1), prices)
        slippage = model.predict([[quantity]])[0] - prices[0]
        print(f"Calculated slippage: {slippage}") 
        return slippage

    def almgen_chriss_impact(self):
        Q = float(self.quantity.text())
        V = sum(v for p,v in self.order_book.bids + self.order_book.asks)
        sigma = std([p for p,v in self.order_book.bids + self.order_book.asks])
        impact = 0.2 * sigma * sqrt(Q/V)
        print(f"Calculated market impact: {impact}") 
        return impact

    def update_metrics(self):
        try:
            print("Updating metrics...")
            start_time = datetime.now() 

            # --- Get Input Parameters ---
            selected_exchange = self.exchange.currentText()
            selected_asset = self.asset.currentText()
            entered_quantity = float(self.quantity.text())  
            selected_order_type = self.order_type.currentText()
            entered_volatility = float(self.volatility.text())  
            selected_fee_tier = self.fee_tier.currentText()

            # --- Calculate Metrics ---
            slippage = self.calculate_slippage()
            fee_rates = {"Tier 1": 0.001, "Tier 2": 0.0008, "Tier 3": 0.0005}
            base_fee_rate = fee_rates.get(selected_fee_tier, 0.001)
            fees = base_fee_rate * entered_quantity 
            impact = self.almgen_chriss_impact() 
            net_cost = slippage + fees + impact
            maker_taker_proportion = 0.8
            end_time = datetime.now()
            internal_latency = (end_time - start_time).total_seconds() * 1000 

            # --- Update UI ---
            self.slippage_label.setText(f"Slippage: ${slippage:.4f}")
            self.fees_label.setText(f"Fees: ${fees:.4f}")
            self.impact_label.setText(f"Market Impact: ${impact:.4f}")
            self.net_cost_label.setText(f"Net Cost: ${net_cost:.4f}")
            self.maker_taker_label.setText(f"Maker/Taker Proportion: {maker_taker_proportion:.2f}") 
            self.latency_label.setText(f"Internal Latency: {internal_latency:.2f} ms")

            print(f"Updated UI with - Slippage: {slippage}, Fees: {fees}, Impact: {impact}, Net Cost: {net_cost}, Maker/Taker: {maker_taker_proportion}, Latency: {internal_latency:.2f} ms")

        except Exception as e:
            print(f"Calculation error: {e}")
            traceback.print_exc() 

    def on_update_button_clicked(self):
        selected_exchange = self.exchange.currentText()
        selected_asset = self.asset.currentText()
        entered_quantity = self.quantity.text()

        print(f"Update button clicked. Attempting to update for:")
        print(f"  Exchange: {selected_exchange}")
        print(f"  Asset: {selected_asset}")
        print(f"  Quantity: {entered_quantity}")

        asyncio.create_task(self.start_websocket_client(selected_exchange, selected_asset))

async def main():
    global window
    print("async main function called.")
    app = QApplication.instance() or QApplication(sys.argv)
    print("QApplication created.")
    window = TradeSimulator()
    print("TradeSimulator window created.")
    window.show()
    print("window.show() called.")

    def simple_task_done_callback(task):
        if task.exception():
            print(f"WebSocket client task failed with exception: {task.exception()}")
            traceback.print_exc()

    try:
        websocket_task = asyncio.create_task(window.start_websocket_client())
        websocket_task.add_done_callback(simple_task_done_callback)
        print("Initial websocket client task created and simple callback added in main.")
    except Exception as e:
        print(f"Error creating initial websocket task: {e}")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    await loop.create_task(asyncio.sleep(float('inf')))  # Keep the event loop running indefinitely

if __name__ == "__main__":
    print("__main__ block executed.") 
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error in main execution: {e}")
        traceback.print_exc()
    print("qasync.run finished.")
