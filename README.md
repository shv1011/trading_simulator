# Cryptocurrency Trade Simulator

## Features
- Real-time L2 order book processing from OKX
- Slippage estimation using Quantile Regression
- Market impact calculation via Almgren-Chriss model
- Taker fee calculation
- Real-time GUI updates

## Requirements
- Python 3.9+
- VPN connection to access OKX

## Installation
- pip install -r requirements.txt

## Usage
- python main.py


## Models Implemented

### Slippage Estimation
- Uses 95th percentile Quantile Regression on order book depth
- Trained on 100ms order book snapshots

### Almgren-Chriss Model
\[ \Delta P = \gamma \sigma \sqrt{\frac{Q}{V}} \]
- \(\gamma = 0.2\) (risk aversion)
- \(\sigma\) = 30-second volatility
- \(Q\) = Order quantity
- \(V\) = Total order book volume

## Performance
- Processes updates within 2ms latency
- Handles 1000+ orders/sec
