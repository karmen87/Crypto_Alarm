#!/usr/bin/env python3
"""
Single-file web application for calculating and visualizing beta, correlation,
and covariance for cryptocurrency assets using MEXC API.
"""

from flask import Flask, render_template_string, request, jsonify
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# Default assets
"""
DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT",
                  "TRXUSDT", "ADAUSDT", "MUSDT",
                  "XRPUSDT", "ZECUSDT", "DASHUSDT",
                  "HYPERUSDT"]


DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT",
                  "STRKUSDT", "ZECUSDT", "XMRUSDT",
                  "METUSDT","RIVERUSDT", "DASHUSDT",
                ]

"""



DEFAULT_ASSETS = [ "XMRUSDT","CCUSDT", "LINKUSDT", "LTCUSDT",
                   "ZECUSDT", "NIGHTUSDT", "DASHUSDT", "XTZUSDT",
                    "DCRUSDT", "BDXUSDT"]



DEFAULT_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
                  "ZKUSDT", "ZECUSDT", "XMRUSDT",  "HYPEUSDT",
                  "NIGHTUSDT", "TAOUSDT", "RIVERUSDT", "RAINUSDT"
                ]


DEFAULT_ASSETS = ["BTCUSDT", "PIUSDT", "SENTUSDT", "HYPEUSDT", "HUSDT" , "KITEUSDT"

                ]

# Lookback window configurations (in minutes)
LOOKBACK_WINDOWS = {
    "5": 5,
    "15": 15,
    "30": 30,
    "60": 60,
    "120": 120,
    "240": 240,
    "720": 720,
    "1440": 1440,  # 1 day
    "2880": 2880,  # 2 days
    "10080": 10080  # 1 week
}

# MEXC API interval mapping (MEXC uses different format than standard)
# Note: MEXC doesn't support 2h or 12h, so we use closest alternatives
INTERVAL_MAP = {
    5: "5m",
    15: "15m",
    30: "30m",
    60: "60m",  # MEXC uses "60m" not "1h"
    120: "60m",  # Use 60m and fetch more data (no 2h available)
    240: "4h",
    720: "4h"  # Use 4h and fetch more data (no 12h available)
}

# Available MEXC API intervals for user selection
AVAILABLE_INTERVALS = [
    ("1m", "1 minute"),
    ("5m", "5 minutes"),
    ("15m", "15 minutes"),
    ("30m", "30 minutes"),
    ("60m", "60 minutes (1 hour)"),
    ("4h", "4 hours"),
    ("1d", "1 day"),
    ("1W", "1 week"),
    ("1M", "1 month")
]

def fetch_klines(symbol, interval, limit=1000):
    """
    Fetch kline data from MEXC API
    """
    url = "https://api.mexc.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Parse kline data: [Open time, Open, High, Low, Close, Volume, Close time, ...]
        df = pd.DataFrame(data, columns=['open_time', 'open', 'high', 'low', 'close',
                                         'volume', 'close_time', 'quote_volume'])
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close'] = df['close'].astype(float)
        df = df[['timestamp', 'close']].set_index('timestamp')

        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {str(e)}")
        return None

def synchronize_timeseries(data_dict):
    """
    Synchronize time series data across all assets to ensure same timestamps
    """
    if not data_dict:
        return None

    # Find common timestamps across all assets
    common_index = None
    for symbol, df in data_dict.items():
        if df is not None:
            if common_index is None:
                common_index = df.index
            else:
                common_index = common_index.intersection(df.index)

    if common_index is None or len(common_index) == 0:
        return None

    # Filter all dataframes to common timestamps
    synchronized_data = {}
    for symbol, df in data_dict.items():
        if df is not None:
            synchronized_data[symbol] = df.loc[common_index]

    return synchronized_data

def calculate_returns(prices_df):
    """
    Calculate percentage returns from price data
    """
    return prices_df.pct_change().dropna()

def calculate_volatility_metrics(prices_df, returns_df):
    """
    Calculate volatility metrics for each asset
    - No trend assumption: volatility of absolute price and price returns
    - Trend assumption: mean, volatility, and R-squared for price and returns
    """
    n = len(prices_df)
    time_index = np.arange(n)

    volatility_data = []

    for col in prices_df.columns:
        prices = prices_df[col].values
        returns = returns_df[col].values

        # No trend assumption
        price_vol_no_trend = np.std(prices, ddof=1)
        returns_vol_no_trend = np.std(returns, ddof=1)

        # Trend assumption - for prices
        # Fit linear regression: price = a + b*time
        price_coeffs = np.polyfit(time_index, prices, 1)
        price_trend = np.polyval(price_coeffs, time_index)
        price_residuals = prices - price_trend
        price_vol_with_trend = np.std(price_residuals, ddof=1)
        price_mean_trend = price_coeffs[0]  # slope

        # R-squared for price
        ss_tot_price = np.sum((prices - np.mean(prices)) ** 2)
        ss_res_price = np.sum(price_residuals ** 2)
        price_r_squared = 1 - (ss_res_price / ss_tot_price) if ss_tot_price != 0 else 0

        # Trend assumption - for returns
        # Fit linear regression: returns = a + b*time
        returns_time_index = np.arange(len(returns))
        returns_coeffs = np.polyfit(returns_time_index, returns, 1)
        returns_trend = np.polyval(returns_coeffs, returns_time_index)
        returns_residuals = returns - returns_trend
        returns_vol_with_trend = np.std(returns_residuals, ddof=1)
        returns_mean_trend = returns_coeffs[0]  # slope

        # R-squared for returns
        ss_tot_returns = np.sum((returns - np.mean(returns)) ** 2)
        ss_res_returns = np.sum(returns_residuals ** 2)
        returns_r_squared = 1 - (ss_res_returns / ss_tot_returns) if ss_tot_returns != 0 else 0

        volatility_data.append({
            'asset': col,
            'price_vol_no_trend': price_vol_no_trend,
            'returns_vol_no_trend': returns_vol_no_trend,
            'price_mean_trend': price_mean_trend,
            'price_vol_with_trend': price_vol_with_trend,
            'price_r_squared': price_r_squared,
            'returns_mean_trend': returns_mean_trend,
            'returns_vol_with_trend': returns_vol_with_trend,
            'returns_r_squared': returns_r_squared
        })

    return pd.DataFrame(volatility_data)

def calculate_statistics(returns_df, prices_df):
    """
    Calculate correlation, covariance, and beta matrices
    """
    # Correlation matrix
    correlation = returns_df.corr()

    # Covariance matrix
    covariance = returns_df.cov()

    # Beta calculation (using first asset as market/benchmark)
    beta_matrix = pd.DataFrame(index=returns_df.columns, columns=returns_df.columns)

    for col in returns_df.columns:
        for benchmark in returns_df.columns:
            if benchmark == col:
                beta_matrix.loc[col, benchmark] = 1.0
            else:
                # Beta = Cov(asset, benchmark) / Var(benchmark)
                cov_val = returns_df[col].cov(returns_df[benchmark])
                var_val = returns_df[benchmark].var()
                beta_matrix.loc[col, benchmark] = cov_val / var_val if var_val != 0 else 0

    beta_matrix = beta_matrix.astype(float)

    # Normalize prices to start at 100
    normalized_prices = (prices_df / prices_df.iloc[0] * 100)

    # Calculate volatility metrics
    volatility_metrics = calculate_volatility_metrics(prices_df, returns_df)

    # Get time range
    time_range = {
        "oldest": prices_df.index.min().strftime("%Y-%m-%d %H:%M:%S"),
        "newest": prices_df.index.max().strftime("%Y-%m-%d %H:%M:%S")
    }

    return {
        "correlation": correlation,
        "covariance": covariance,
        "beta": beta_matrix,
        "volatility_metrics": volatility_metrics,
        "normalized_prices": normalized_prices,
        "time_range": time_range
    }

@app.route('/')
def index():
    """
    Render the main page
    """
    default_assets_str = ", ".join(DEFAULT_ASSETS)
    return render_template_string(
        HTML_TEMPLATE,
        default_assets=default_assets_str,
        lookback_windows=LOOKBACK_WINDOWS,
        available_intervals=AVAILABLE_INTERVALS
    )

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Perform analysis based on user inputs
    """
    try:
        data = request.json
        lookback_window = int(data.get('lookback_window', 60))
        extra_assets = data.get('extra_assets', [])

        # Get interval from request, or fall back to INTERVAL_MAP
        interval = data.get('interval')
        if not interval:
            interval = INTERVAL_MAP.get(lookback_window, "60m")

        # Combine default and extra assets
        all_assets = DEFAULT_ASSETS + [asset.strip().upper() for asset in extra_assets if asset.strip()]
        all_assets = list(dict.fromkeys(all_assets))  # Remove duplicates while preserving order

        # Fetch data for all assets
        raw_data = {}
        for symbol in all_assets:
            df = fetch_klines(symbol, interval, limit=1000)
            if df is not None and not df.empty:
                raw_data[symbol] = df

        if not raw_data:
            return jsonify({"error": "Failed to fetch data for any assets"}), 400

        # Synchronize time series
        synchronized_data = synchronize_timeseries(raw_data)

        if not synchronized_data:
            return jsonify({"error": "Failed to synchronize time series data"}), 400

        # Create combined price dataframe
        prices_df = pd.DataFrame({symbol: df['close'] for symbol, df in synchronized_data.items()})

        # Truncate data to lookback window
        # Calculate the cutoff time based on lookback window in minutes
        if len(prices_df) > 0:
            latest_time = prices_df.index.max()
            cutoff_time = latest_time - timedelta(minutes=lookback_window)
            prices_df = prices_df[prices_df.index >= cutoff_time]

            # Ensure we have enough data points for statistical calculations
            # Need at least 3 points: 1 for initial price + 2 returns for covariance calculation
            if len(prices_df) < 3:
                return jsonify({"error": f"Not enough data points ({len(prices_df)}) in {lookback_window} minute window. Need at least 3 data points. Try a longer lookback window or smaller interval."}), 400

        # Calculate returns
        returns_df = calculate_returns(prices_df)

        # Validate that we have enough returns for statistics (need at least 2 returns)
        if len(returns_df) < 2:
            return jsonify({"error": f"Not enough return data points ({len(returns_df)}) for statistical analysis. Need at least 2 returns. Try a longer lookback window or smaller interval."}), 400

        # Calculate statistics
        stats = calculate_statistics(returns_df, prices_df)

        # Replace NaN values with None (which converts to null in JSON)
        correlation_dict = stats["correlation"].replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict()
        covariance_dict = stats["covariance"].replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict()
        beta_dict = stats["beta"].replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict()
        volatility_dict = stats["volatility_metrics"].replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient='records')

        # Prepare response - convert to proper JSON-serializable format
        response = {
            "correlation": correlation_dict,
            "covariance": covariance_dict,
            "beta": beta_dict,
            "volatility_metrics": volatility_dict,
            "normalized_prices": {
                "timestamps": [ts.strftime("%Y-%m-%d %H:%M") for ts in stats["normalized_prices"].index],
                "data": {col: stats["normalized_prices"][col].replace({np.nan: None, np.inf: None, -np.inf: None}).tolist() for col in stats["normalized_prices"].columns}
            },
            "time_range": stats["time_range"],
            "assets": all_assets
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Asset Analysis</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }

        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
        }

        .controls {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
        }

        .control-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            font-weight: bold;
            margin-bottom: 8px;
            color: #555;
        }

        select, input, button {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
            transition: border-color 0.3s;
        }

        select:focus, input:focus {
            outline: none;
            border-color: #667eea;
        }

        .assets-input {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .asset-tag {
            background: #667eea;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .asset-tag button {
            background: transparent;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 18px;
            width: auto;
            padding: 0;
        }

        button.analyze-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
            font-size: 18px;
            margin-top: 10px;
            transition: transform 0.2s;
        }

        button.analyze-btn:hover {
            transform: translateY(-2px);
        }

        button.analyze-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .results {
            margin-top: 30px;
        }

        .time-range {
            background: #e8f5e9;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
            color: #2e7d32;
        }

        .matrix-container {
            margin-bottom: 40px;
        }

        .matrix-title {
            font-size: 1.5em;
            color: #333;
            margin-bottom: 15px;
            text-align: center;
        }

        .chart-container {
            margin-bottom: 40px;
        }

        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #c62828;
        }

        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.2em;
            color: #667eea;
        }

        .default-assets {
            background: #fff3e0;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #ff9800;
        }

        .default-assets strong {
            color: #e65100;
        }

        input[type="text"] {
            margin-bottom: 10px;
        }

        .add-asset-btn {
            background: #4caf50;
            color: white;
            border: none;
            cursor: pointer;
            margin-top: 5px;
        }

        .extra-assets-list {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }

        .volatility-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }

        .volatility-table th {
            background: #667eea;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            border: 1px solid #ddd;
            cursor: pointer;
            user-select: none;
            position: relative;
        }

        .volatility-table th:hover {
            background: #5568d3;
        }

        .volatility-table th.sortable::after {
            content: ' ⇅';
            opacity: 0.5;
        }

        .volatility-table th.sorted-asc::after {
            content: ' ▲';
            opacity: 1;
        }

        .volatility-table th.sorted-desc::after {
            content: ' ▼';
            opacity: 1;
        }

        .volatility-table td {
            padding: 10px 8px;
            border: 1px solid #ddd;
            text-align: right;
        }

        .volatility-table tr:nth-child(even) {
            background: #f8f9fa;
        }

        .volatility-table tr:hover {
            background: #e9ecef;
        }

        .volatility-table .asset-col {
            font-weight: bold;
            text-align: left;
            color: #667eea;
        }

        .section-header {
            background: #495057;
            color: white;
            text-align: center;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Crypto Asset Analysis</h1>

        <div class="controls">
            <div class="default-assets">
                <strong>Default Assets:</strong> {{ default_assets }}
            </div>

            <div class="control-group">
                <label for="lookbackWindow">Lookback Window</label>
                <select id="lookbackWindow">
                    {% for key, value in lookback_windows.items() %}
                    <option value="{{ key }}" {% if key == "60" %}selected{% endif %}>
                        {% if value == 60 %}1 hour
                        {% elif value == 120 %}2 hours
                        {% elif value == 240 %}4 hours
                        {% elif value == 720 %}12 hours
                        {% elif value == 1440 %}1 day
                        {% elif value == 2880 %}2 days
                        {% elif value == 10080 %}1 week
                        {% else %}{{ value }} minutes
                        {% endif %}
                    </option>
                    {% endfor %}
                </select>
            </div>

            <div class="control-group">
                <label for="intervalMap">MEXC API Interval</label>
                <select id="intervalMap">
                    {% for interval_value, interval_label in available_intervals %}
                    <option value="{{ interval_value }}" {% if interval_value == "60m" %}selected{% endif %}>
                        {{ interval_label }}
                    </option>
                    {% endfor %}
                </select>
            </div>

            <div class="control-group">
                <label for="extraAssets">Add Extra Assets (e.g., BNBUSDT, XRPUSDT)</label>
                <input type="text" id="extraAssets" placeholder="Enter asset symbol (e.g., BNBUSDT)">
                <button class="add-asset-btn" onclick="addAsset()">Add Asset</button>
                <div class="extra-assets-list" id="extraAssetsList"></div>
            </div>

            <div class="control-group">
                <label for="volatilityScale">Volatility Scale Factor (e.g., 252 for annual, 365 for days)</label>
                <input type="number" id="volatilityScale" value="1" min="0.001" step="any" placeholder="Enter scale factor">
            </div>

            <button class="analyze-btn" onclick="analyze()">Analyze Assets</button>
        </div>

        <div id="results" class="results" style="display: none;">
            <div id="timeRange" class="time-range"></div>

            <div class="matrix-container">
                <h2 class="matrix-title">Correlation Matrix</h2>
                <div id="correlationMatrix"></div>
            </div>

            <div class="matrix-container">
                <h2 class="matrix-title">Covariance Matrix</h2>
                <div id="covarianceMatrix"></div>
            </div>

            <div class="matrix-container">
                <h2 class="matrix-title">Beta Matrix</h2>
                <div id="betaMatrix"></div>
            </div>

            <div class="matrix-container">
                <h2 class="matrix-title">Volatility Metrics</h2>
                <div id="volatilityTable"></div>
            </div>

            <div class="chart-container">
                <h2 class="matrix-title">Normalized Price Chart (Base = 100%)</h2>
                <div id="priceChart"></div>
            </div>
        </div>

        <div id="error" class="error" style="display: none;"></div>
        <div id="loading" class="loading" style="display: none;">Loading and analyzing data...</div>
    </div>

    <script>
        let extraAssets = [];

        function addAsset() {
            const input = document.getElementById('extraAssets');
            const asset = input.value.trim().toUpperCase();

            if (asset && !extraAssets.includes(asset)) {
                extraAssets.push(asset);
                updateExtraAssetsList();
                input.value = '';
            }
        }

        function removeAsset(asset) {
            extraAssets = extraAssets.filter(a => a !== asset);
            updateExtraAssetsList();
        }

        function updateExtraAssetsList() {
            const list = document.getElementById('extraAssetsList');
            list.innerHTML = extraAssets.map(asset =>
                `<div class="asset-tag">
                    ${asset}
                    <button onclick="removeAsset('${asset}')">&times;</button>
                </div>`
            ).join('');
        }

        function createHeatmap(data, assets, title, colorscale = 'RdBu', reversescale = false, focusOffDiagonal = false) {
            const z = assets.map(asset1 =>
                assets.map(asset2 => data[asset1][asset2])
            );

            const trace = {
                z: z,
                x: assets,
                y: assets,
                type: 'heatmap',
                colorscale: colorscale,
                reversescale: reversescale,
                text: z.map(row => row.map(val => val.toFixed(6))),
                texttemplate: '%{text}',
                textfont: {
                    size: 10
                },
                hovertemplate: '<b>%{y}</b> vs <b>%{x}</b><br>Value: %{z:.6f}<extra></extra>'
            };

            const layout = {
                xaxis: {
                    side: 'bottom'
                },
                yaxis: {
                    autorange: 'reversed'
                },
                margin: {
                    l: 100,
                    r: 50,
                    t: 50,
                    b: 100
                },
                height: 500
            };

            // For covariance: set color scale based on off-diagonal values only
            if (focusOffDiagonal) {
                // Extract off-diagonal elements
                const offDiagonal = [];
                for (let i = 0; i < z.length; i++) {
                    for (let j = 0; j < z[i].length; j++) {
                        if (i !== j) {
                            offDiagonal.push(z[i][j]);
                        }
                    }
                }

                // Calculate percentiles for better color distribution
                offDiagonal.sort((a, b) => a - b);
                const p5 = offDiagonal[Math.floor(offDiagonal.length * 0.05)];
                const p95 = offDiagonal[Math.floor(offDiagonal.length * 0.95)];

                // Make symmetric around 0 for better visualization
                const maxAbs = Math.max(Math.abs(p5), Math.abs(p95));

                trace.zmin = -maxAbs;
                trace.zmax = maxAbs;
                trace.zauto = false;
            }

            return { data: [trace], layout: layout };
        }

        function createLineChart(timestamps, data, assets) {
            const traces = assets.map(asset => ({
                x: timestamps,
                y: data[asset],
                type: 'scatter',
                mode: 'lines',
                name: asset,
                line: {
                    width: 2
                }
            }));

            const layout = {
                xaxis: {
                    title: 'Time',
                    showgrid: true
                },
                yaxis: {
                    title: 'Normalized Price (%)',
                    showgrid: true
                },
                hovermode: 'x unified',
                margin: {
                    l: 80,
                    r: 50,
                    t: 50,
                    b: 80
                },
                height: 500,
                legend: {
                    x: 0,
                    y: 1,
                    bgcolor: 'rgba(255,255,255,0.8)'
                }
            };

            return { data: traces, layout: layout };
        }

        let currentVolatilityData = [];
        let currentSortColumn = null;
        let currentSortDirection = 'asc';

        function createVolatilityTable(volatilityData, scale) {
            currentVolatilityData = volatilityData.map(row => ({
                ...row,
                scale: scale,
                sqrtScale: Math.sqrt(scale)
            }));

            let html = '<table class="volatility-table" id="volatilityTableElement">';
            html += '<thead><tr>';
            html += '<th rowspan="3" class="asset-col sortable" data-column="asset">Asset</th>';
            html += '<th colspan="2" class="section-header">No Trend Assumption</th>';
            html += '<th colspan="6" class="section-header">With Trend Assumption</th>';
            html += '</tr><tr>';
            html += '<th rowspan="2" class="sortable" data-column="price_vol_no_trend_scaled">Price Vol</th>';
            html += '<th rowspan="2" class="sortable" data-column="returns_vol_no_trend_scaled">Returns Vol</th>';
            html += '<th colspan="3" class="section-header">Price</th>';
            html += '<th colspan="3" class="section-header">Returns</th>';
            html += '</tr><tr>';
            html += '<th class="sortable" data-column="price_mean_trend_scaled">Mean</th>';
            html += '<th class="sortable" data-column="price_vol_with_trend_scaled">Vol</th>';
            html += '<th class="sortable" data-column="price_r_squared">R²</th>';
            html += '<th class="sortable" data-column="returns_mean_trend_scaled">Mean</th>';
            html += '<th class="sortable" data-column="returns_vol_with_trend_scaled">Vol</th>';
            html += '<th class="sortable" data-column="returns_r_squared">R²</th>';
            html += '</tr></thead>';
            html += '<tbody id="volatilityTableBody">';

            currentVolatilityData.forEach(row => {
                html += '<tr>';
                html += `<td class="asset-col">${row.asset}</td>`;
                // No trend
                html += `<td>${(row.price_vol_no_trend * row.sqrtScale).toExponential(4)}</td>`;
                html += `<td>${(row.returns_vol_no_trend * row.sqrtScale).toExponential(4)}</td>`;
                // With trend - Price
                html += `<td>${(row.price_mean_trend * row.scale).toExponential(4)}</td>`;
                html += `<td>${(row.price_vol_with_trend * row.sqrtScale).toExponential(4)}</td>`;
                html += `<td>${row.price_r_squared.toFixed(6)}</td>`;
                // With trend - Returns
                html += `<td>${(row.returns_mean_trend * row.scale).toExponential(4)}</td>`;
                html += `<td>${(row.returns_vol_with_trend * row.sqrtScale).toExponential(4)}</td>`;
                html += `<td>${row.returns_r_squared.toFixed(6)}</td>`;
                html += '</tr>';
            });

            html += '</tbody></table>';
            return html;
        }

        function sortVolatilityTable(column) {
            // Toggle sort direction if clicking the same column
            if (currentSortColumn === column) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = column;
                currentSortDirection = 'asc';
            }

            // Calculate scaled values for sorting
            const dataWithScaled = currentVolatilityData.map(row => {
                const sqrtScale = Math.sqrt(row.scale);
                return {
                    ...row,
                    price_vol_no_trend_scaled: row.price_vol_no_trend * sqrtScale,
                    returns_vol_no_trend_scaled: row.returns_vol_no_trend * sqrtScale,
                    price_mean_trend_scaled: row.price_mean_trend * row.scale,
                    price_vol_with_trend_scaled: row.price_vol_with_trend * sqrtScale,
                    returns_mean_trend_scaled: row.returns_mean_trend * row.scale,
                    returns_vol_with_trend_scaled: row.returns_vol_with_trend * sqrtScale
                };
            });

            // Sort the data
            dataWithScaled.sort((a, b) => {
                let aVal = a[column];
                let bVal = b[column];

                // Handle string comparison for asset names
                if (typeof aVal === 'string') {
                    return currentSortDirection === 'asc'
                        ? aVal.localeCompare(bVal)
                        : bVal.localeCompare(aVal);
                }

                // Numeric comparison
                return currentSortDirection === 'asc' ? aVal - bVal : bVal - aVal;
            });

            // Update the table body
            let html = '';
            dataWithScaled.forEach(row => {
                html += '<tr>';
                html += `<td class="asset-col">${row.asset}</td>`;
                // No trend
                html += `<td>${row.price_vol_no_trend_scaled.toExponential(4)}</td>`;
                html += `<td>${row.returns_vol_no_trend_scaled.toExponential(4)}</td>`;
                // With trend - Price
                html += `<td>${row.price_mean_trend_scaled.toExponential(4)}</td>`;
                html += `<td>${row.price_vol_with_trend_scaled.toExponential(4)}</td>`;
                html += `<td>${row.price_r_squared.toFixed(6)}</td>`;
                // With trend - Returns
                html += `<td>${row.returns_mean_trend_scaled.toExponential(4)}</td>`;
                html += `<td>${row.returns_vol_with_trend_scaled.toExponential(4)}</td>`;
                html += `<td>${row.returns_r_squared.toFixed(6)}</td>`;
                html += '</tr>';
            });

            document.getElementById('volatilityTableBody').innerHTML = html;

            // Update header styling
            document.querySelectorAll('.volatility-table th.sortable').forEach(th => {
                th.classList.remove('sorted-asc', 'sorted-desc');
                if (th.dataset.column === column) {
                    th.classList.add(currentSortDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
                }
            });
        }

        function attachSortHandlers() {
            document.querySelectorAll('.volatility-table th.sortable').forEach(th => {
                th.addEventListener('click', () => {
                    const column = th.dataset.column;
                    sortVolatilityTable(column);
                });
            });
        }

        async function analyze() {
            const lookbackWindow = document.getElementById('lookbackWindow').value;
            const intervalMap = document.getElementById('intervalMap').value;
            const scale = parseFloat(document.getElementById('volatilityScale').value) || 1;
            const analyzeBtn = document.querySelector('.analyze-btn');
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const results = document.getElementById('results');

            // Hide previous results and errors
            results.style.display = 'none';
            error.style.display = 'none';
            loading.style.display = 'block';
            analyzeBtn.disabled = true;

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        lookback_window: parseInt(lookbackWindow),
                        interval: intervalMap,
                        extra_assets: extraAssets
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Analysis failed');
                }

                // Display time range
                document.getElementById('timeRange').innerHTML =
                    `Data Range: <strong>${data.time_range.oldest}</strong> to <strong>${data.time_range.newest}</strong>`;

                // Create correlation heatmap
                const corrPlot = createHeatmap(data.correlation, data.assets, 'Correlation', 'RdBu', true);
                Plotly.newPlot('correlationMatrix', corrPlot.data, corrPlot.layout, {responsive: true});

                // Create covariance heatmap with signed log transformation
                const covPlot = createHeatmap(data.covariance, data.assets, 'Covariance', 'Viridis', false, true);
                Plotly.newPlot('covarianceMatrix', covPlot.data, covPlot.layout, {responsive: true});

                // Create beta heatmap
                const betaPlot = createHeatmap(data.beta, data.assets, 'Beta', 'RdYlGn', true);
                Plotly.newPlot('betaMatrix', betaPlot.data, betaPlot.layout, {responsive: true});

                // Create volatility table
                const volatilityTableHtml = createVolatilityTable(data.volatility_metrics, scale);
                document.getElementById('volatilityTable').innerHTML = volatilityTableHtml;

                // Attach sort handlers after table is created
                attachSortHandlers();

                // Create normalized price chart
                const pricePlot = createLineChart(
                    data.normalized_prices.timestamps,
                    data.normalized_prices.data,
                    data.assets
                );
                Plotly.newPlot('priceChart', pricePlot.data, pricePlot.layout, {responsive: true});

                // Show results
                results.style.display = 'block';

            } catch (err) {
                error.textContent = `Error: ${err.message}`;
                error.style.display = 'block';
            } finally {
                loading.style.display = 'none';
                analyzeBtn.disabled = false;
            }
        }

        // Allow Enter key to add assets
        document.getElementById('extraAssets').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                addAsset();
            }
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("Starting Crypto Asset Analysis Web Application...")
    print("Open your browser and navigate to: http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)