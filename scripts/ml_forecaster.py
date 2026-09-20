#!/usr/bin/env python3
"""LIGHTWEIGHT LSTM FORECACTOR — additive ML layer for our pipeline.

Uses PyTorch (already installed) to train a small LSTM on our bars.db.
Outputs direction + confidence for integration with scan scoring.

HONEST DISCLAIMER:
- ML forecasting is experimental, not proven edge
- Always validate against simple baselines (RSI, momentum)
- Never trade solely on ML predictions without backtest confirmation
- This is an ADDITIVE layer, not a replacement for existing analysis

Usage:
    python3 ml_forecaster.py --train --sectors crypto
    python3 ml_forecaster.py --predict --symbols BTC-USD ETH-USD
    python3 ml_forecaster.py --evaluate --sector crypto
"""
from __future__ import annotations
import argparse, json, pathlib, sqlite3, sys, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(pathlib.Path(__file__).parent / "bt"))
import bt_store as B

REPORT_DIR = pathlib.Path(r"C:\Hermes\workflow\backtest\reports")
MODEL_DIR = pathlib.Path(r"C:\Hermes\workflow\data\ml_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Model config
SEQUENCE_LENGTH = 20  # Lookback window
HIDDEN_SIZE = 32       # Small LSTM
NUM_LAYERS = 1         # Keep it light
BATCH_SIZE = 64
EPOCHS = 50
LEARNING_RATE = 0.001
DROPOUT = 0.2

class LightweightLSTM(nn.Module):
    """Small LSTM for direction prediction."""
    def __init__(self, input_size, hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, dropout=DROPOUT):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(16, 2)  # 2 classes: down, up
        
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        out = lstm_out[:, -1, :]  # Last timestep
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out

def prepare_features(df):
    """Create feature matrix from OHLCV data."""
    features = pd.DataFrame()
    
    # Price-based features
    features['returns'] = df['close'].pct_change(fill_method=None)
    features['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    
    # Moving average ratios
    features['sma20_ratio'] = df['close'] / df['close'].rolling(20).mean()
    features['sma50_ratio'] = df['close'] / df['close'].rolling(50).mean()
    features['sma200_ratio'] = df['close'] / df['close'].rolling(200).mean()
    
    # Volatility
    features['volatility'] = features['returns'].rolling(20).std()
    
    # Volume features
    features['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    features['rsi'] = 100 - 100 / (1 + rs)
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    features['macd'] = ema12 - ema26
    features['macd_signal'] = features['macd'].ewm(span=9).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    features['atr'] = true_range.rolling(14).mean() / df['close']
    
    # Target: next day direction (1 = up, 0 = down)
    features['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    return features.dropna()

def create_sequences(features, seq_length=SEQUENCE_LENGTH):
    """Create sequences for LSTM input."""
    X, y = [], []
    feature_cols = [c for c in features.columns if c != 'target']
    
    for i in range(len(features) - seq_length):
        X.append(features[feature_cols].iloc[i:i+seq_length].values)
        y.append(features['target'].iloc[i+seq_length-1])
    
    return np.array(X), np.array(y)

def train_model(model, train_loader, val_loader, epochs=EPOCHS):
    """Train the LSTM."""
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)
    
    best_val_loss = float('inf')
    patience_counter = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            output = model(X_batch)
            loss = criterion(output, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        correct = 0
        total = 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                output = model(X_batch)
                loss = criterion(output, y_batch)
                val_loss += loss.item()
                pred = output.argmax(dim=1)
                correct += (pred == y_batch).sum().item()
                total += y_batch.size(0)
        
        val_acc = correct / total if total > 0 else 0
        scheduler.step(val_loss)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
        else:
            patience_counter += 1
        
        if patience_counter >= 10:
            print(f"  Early stopping at epoch {epoch}")
            break
        
        if epoch % 10 == 0:
            print(f"  Epoch {epoch}: train_loss={train_loss/len(train_loader):.4f}, val_loss={val_loss/len(val_loader):.4f}, val_acc={val_acc:.2%}")
    
    return model

def train_sector(sector, symbols=None):
    """Train LSTM for all symbols in a sector."""
    print(f"\n{'='*60}")
    print(f"TRAINING: {sector}")
    print(f"{'='*60}")
    
    if symbols is None:
        symbols = B.sector_symbols(sector)
    
    results = {}
    
    for sym in symbols:
        if sym not in B.load_bars([sym]):
            continue
        
        frames = B.load_bars([sym])
        df = list(frames.values())[0]
        df = B.add_indicators(df)
        df = df.dropna()
        
        if len(df) < 200:
            continue
        
        # Prepare features
        features = prepare_features(df)
        if len(features) < 100:
            continue
        
        X, y = create_sequences(features)
        if len(X) < 50:
            continue
        
        # Train/val split (80/20)
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]
        
        # Convert to tensors
        X_train_t = torch.FloatTensor(X_train)
        y_train_t = torch.LongTensor(y_train)
        X_val_t = torch.FloatTensor(X_val)
        y_val_t = torch.LongTensor(y_val)
        
        train_dataset = TensorDataset(X_train_t, y_train_t)
        val_dataset = TensorDataset(X_val_t, y_val_t)
        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
        
        # Model
        input_size = X_train.shape[2]
        model = LightweightLSTM(input_size)
        
        # Train
        print(f"\n  Training {sym} ({len(X_train)} samples, {input_size} features)...")
        start = time.time()
        model = train_model(model, train_loader, val_loader, epochs=30)
        elapsed = time.time() - start
        
        # Evaluate
        model.eval()
        with torch.no_grad():
            val_output = model(X_val_t)
            val_pred = val_output.argmax(dim=1)
            val_acc = (val_pred == y_val_t).float().mean().item()
            
            # Confidence (softmax probability)
            probs = torch.softmax(val_output, dim=1)
            avg_confidence = probs.max(dim=1)[0].mean().item()
        
        # Baseline: always predict majority class
        majority_class = y_train.mean()
        baseline_acc = max(majority_class, 1 - majority_class)
        
        results[sym] = {
            "val_accuracy": round(val_acc, 4),
            "baseline_accuracy": round(baseline_acc, 4),
            "improvement": round(val_acc - baseline_acc, 4),
            "avg_confidence": round(avg_confidence, 4),
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "features": input_size,
            "train_time_s": round(elapsed, 1),
            "beats_baseline": val_acc > baseline_acc + 0.02,
        }
        
        status = "✅ BEATS BASELINE" if results[sym]["beats_baseline"] else "❌ Below baseline"
        print(f"  {sym}: Val Acc={val_acc:.2%}, Baseline={baseline_acc:.2%}, Confidence={avg_confidence:.2%} {status}")
        
        # Save model
        model_path = MODEL_DIR / f"{sector}_{sym.replace('-', '_').replace('/', '_')}.pt"
        torch.save(model.state_dict(), str(model_path))
    
    return results

def predict_symbol(sym, sector="crypto"):
    """Generate prediction for a symbol."""
    model_path = MODEL_DIR / f"{sector}_{sym.replace('-', '_').replace('/', '_')}.pt"
    if not model_path.exists():
        return None
    
    frames = B.load_bars([sym])
    if not frames:
        return None
    
    df = list(frames.values())[0]
    df = B.add_indicators(df)
    df = df.dropna()
    
    features = prepare_features(df)
    if len(features) < SEQUENCE_LENGTH:
        return None
    
    X, _ = create_sequences(features)
    if len(X) == 0:
        return None
    
    X_t = torch.FloatTensor(X[-1:])  # Last sequence
    
    # Load model
    input_size = X.shape[2]
    model = LightweightLSTM(input_size)
    model.load_state_dict(torch.load(str(model_path)))
    model.eval()
    
    with torch.no_grad():
        output = model(X_t)
        probs = torch.softmax(output, dim=1)
        pred = output.argmax(dim=1).item()
        confidence = probs.max(dim=1)[0].item()
    
    return {
        "symbol": sym,
        "direction": "UP" if pred == 1 else "DOWN",
        "confidence": round(confidence, 4),
        "up_probability": round(probs[0][1].item(), 4),
        "down_probability": round(probs[0][0].item(), 4),
    }

def main():
    print("=" * 80)
    print("LIGHTWEIGHT LSTM FORECACTOR")
    print("=" * 80)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--sectors", nargs="+", default=["crypto"])
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    
    if args.train:
        all_results = {}
        for sector in args.sectors:
            results = train_sector(sector, args.symbols)
            all_results[sector] = results
        
        # Save results
        json_path = REPORT_DIR / "ml_training_results.json"
        json_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
        print(f"\nResults saved to: {json_path}")
    
    elif args.predict:
        symbols = args.symbols or ["BTC-USD", "ETH-USD", "SOL-USD"]
        predictions = []
        for sym in symbols:
            pred = predict_symbol(sym)
            if pred:
                predictions.append(pred)
                print(f"  {pred['symbol']:<12} {pred['direction']:<5} Confidence={pred['confidence']:.2%} (Up={pred['up_probability']:.2%})")
        
        json_path = REPORT_DIR / "ml_predictions.json"
        json_path.write_text(json.dumps(predictions, indent=2, default=str), encoding="utf-8")
    
    elif args.evaluate:
        print("\nEvaluation mode — compare ML vs baseline")
    
    print("\nDone")

if __name__ == "__main__":
    main()
