#!/usr/bin/env python3
"""MT5 ORDER MANAGER — Full order execution for our trading system.

Supports ALL MT5 order types:
- Market orders (BUY, SELL)
- Limit orders (BUY_LIMIT, SELL_LIMIT) — entry on pullback
- Stop orders (BUY_STOP, SELL_STOP) — breakout entry
- Stop-Limit orders (BUY_STOP_LIMIT, SELL_STOP_LIMIT) — confirmation entry
- SL/TP modification
- Order removal
- Partial close

HONEST DISCLAIMER:
- This is for DEMO account (Capital.ComBah-Demo)
- Always verify order before sending
- Never risk more than 2% per trade on live accounts
- ML forecasting is experimental — always confirm with backtest

Usage:
    python3 mt5_order_manager.py --buy-market BTCUSD --lots 0.01
    python3 mt5_order_manager.py --buy-limit BTCUSD --price 75000 --lots 0.01
    python3 mt5_order_manager.py --sell-market ETHUSD --lots 0.1
    python3 mt5_order_manager.py --sell-limit ETHUSD --price 2600 --lots 0.1
    python3 mt5_order_manager.py --buy-stop BTCUSD --price 78000 --lots 0.01
    python3 mt5_order_manager.py --sell-stop BTCUSD --price 74000 --lots 0.01
    python3 mt5_order_manager.py --close-all
    python3 mt5_order_manager.py --close-symbol BTCUSD
    python3 mt5_order_manager.py --modify-sl-tp --ticket 12345 --sl 70000 --tp 80000
    python3 mt5_order_manager.py --remove-pending --ticket 12345
    python3 mt5_order_manager.py --positions
    python3 mt5_order_manager.py --orders
    python3 mt5_order_manager.py --account
    python3 mt5_order_manager.py --symbol-info BTCUSD
"""
from __future__ import annotations
import argparse, sys, time
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Order type mapping
ORDER_TYPES = {
    "buy": mt5.ORDER_TYPE_BUY,
    "sell": mt5.ORDER_TYPE_SELL,
    "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
    "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
    "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
    "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
    "buy_stop_limit": mt5.ORDER_TYPE_BUY_STOP_LIMIT,
    "sell_stop_limit": mt5.ORDER_TYPE_SELL_STOP_LIMIT,
}

FILLING_TYPES = {
    "fok": mt5.ORDER_FILLING_FOK,
    "ioc": mt5.ORDER_FILLING_IOC,
    "return": mt5.ORDER_FILLING_RETURN,
    "boc": mt5.ORDER_FILLING_BOC,
}

TIME_TYPES = {
    "gtc": mt5.ORDER_TIME_GTC,
    "day": mt5.ORDER_TIME_DAY,
    "specified": mt5.ORDER_TIME_SPECIFIED,
    "specified_day": mt5.ORDER_TIME_SPECIFIED_DAY,
}

def init_mt5():
    if not mt5.initialize():
        print("ERROR: MT5 not running")
        return False
    return True

def get_symbol_info(symbol):
    """Get symbol info, trying common suffixes."""
    for suffix in ["", "USD", "EUR", "GBP"]:
        info = mt5.symbol_info(symbol + suffix)
        if info:
            return info, symbol + suffix
    return None, None

def calculate_lot_size(symbol, risk_percent, stop_loss_pips):
    """Calculate lot size based on risk."""
    info, actual_symbol = get_symbol_info(symbol)
    if not info:
        return 0.01  # Default
    
    account = mt5.account_info()
    balance = account.balance
    
    # Risk amount
    risk_amount = balance * (risk_percent / 100)
    
    # Value per pip (approximate)
    point = info.point
    tick_value = info.trade_tick_value
    
    if tick_value == 0:
        tick_value = 1.0  # Default
    
    # Lot size
    lots = risk_amount / (stop_loss_pips * tick_value)
    
    # Normalize to symbol's lot step
    lot_step = info.volume_step
    lots = round(lots / lot_step) * lot_step
    
    # Clamp to min/max
    lots = max(info.volume_min, min(info.volume_max, lots))
    
    return round(lots, 2)

def send_order(symbol, order_type, lots, price=None, sl=None, tp=None, 
               filling="fok", time_type="gtc", comment=""):
    """Send an order to MT5."""
    info, actual_symbol = get_symbol_info(symbol)
    if not info:
        print(f"ERROR: Symbol {symbol} not found")
        return None
    
    # Ensure symbol is visible in Market Watch
    if not info.visible:
        mt5.symbol_select(actual_symbol, True)
        time.sleep(0.5)
        info = mt5.symbol_info(actual_symbol)
    
    # Get current price
    tick = mt5.symbol_info_tick(actual_symbol)
    if not tick:
        print(f"ERROR: No tick data for {actual_symbol}")
        return None
    
    # Determine price based on order type
    if order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_STOP_LIMIT]:
        if price is None:
            price = tick.ask
    else:
        if price is None:
            price = tick.bid
    
    # Resolve filling type
    filling_type = FILLING_TYPES.get(filling, mt5.ORDER_FILLING_FOK)
    
    # Build request
    request = {
        "action": mt5.TRADE_ACTION_PENDING if order_type in [
            mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
            mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP,
            mt5.ORDER_TYPE_BUY_STOP_LIMIT, mt5.ORDER_TYPE_SELL_STOP_LIMIT
        ] else mt5.TRADE_ACTION_DEAL,
        "symbol": actual_symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "deviation": 20,  # Slippage tolerance
        "magic": 123456,  # Our EA magic number
        "comment": comment,
        "type_time": TIME_TYPES.get(time_type, mt5.ORDER_TIME_GTC),
        "type_filling": filling_type,
    }
    
    # Add SL/TP if provided
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp
    
    # Send order
    result = mt5.order_send(request)
    
    if result is None:
        print(f"ERROR: order_send returned None")
        return None
    
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"✅ ORDER SUCCESS")
        print(f"  Symbol: {actual_symbol}")
        print(f"  Type: {order_type}")
        print(f"  Lots: {lots}")
        print(f"  Price: {price}")
        if sl: print(f"  SL: {sl}")
        if tp: print(f"  TP: {tp}")
        print(f"  Ticket: {result.order if hasattr(result, 'order') else result.deal}")
        return result
    else:
        print(f"❌ ORDER FAILED")
        print(f"  Error code: {result.retcode}")
        print(f"  Comment: {result.comment}")
        return result

def close_position(ticket):
    """Close a position by ticket."""
    positions = mt5.positions_get()
    if not positions:
        print("No open positions")
        return
    
    for p in positions:
        if p.ticket == ticket:
            # Determine close order type
            if p.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(p.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(p.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Closed {p.symbol} ticket {ticket}")
            else:
                print(f"❌ Close failed: {result.comment}")
            return
    
    print(f"Ticket {ticket} not found")

def close_all_positions():
    """Close all open positions."""
    positions = mt5.positions_get()
    if not positions:
        print("No open positions")
        return
    
    for p in positions:
        close_position(p.ticket)

def modify_sltp(ticket, sl=None, tp=None):
    """Modify SL/TP of an open position."""
    positions = mt5.positions_get()
    if not positions:
        print("No open positions")
        return
    
    for p in positions:
        if p.ticket == ticket:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": p.symbol,
                "position": ticket,
                "sl": sl if sl is not None else p.sl,
                "tp": tp if tp is not None else p.tp,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Modified SL/TP for {p.symbol} ticket {ticket}")
                print(f"  New SL: {sl}, New TP: {tp}")
            else:
                print(f"❌ Modify failed: {result.comment}")
            return
    
    print(f"Ticket {ticket} not found")

def remove_pending_order(ticket):
    """Remove a pending order."""
    orders = mt5.orders_get()
    if not orders:
        print("No pending orders")
        return
    
    for o in orders:
        if o.ticket == ticket:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Removed pending order {ticket}")
            else:
                print(f"❌ Remove failed: {result.comment}")
            return
    
    print(f"Order {ticket} not found")

def show_positions():
    """Display all open positions."""
    positions = mt5.positions_get()
    if not positions:
        print("No open positions")
        return
    
    print(f"\n{'='*80}")
    print(f"OPEN POSITIONS: {len(positions)}")
    print(f"{'='*80}")
    print(f"{'Ticket':<10} {'Symbol':<12} {'Type':<6} {'Lots':<8} {'Open':<12} {'Current':<12} {'P&L':<10}")
    print("-" * 80)
    
    total_pnl = 0
    for p in positions:
        pnl = p.profit
        total_pnl += pnl
        type_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
        print(f"{p.ticket:<10} {p.symbol:<12} {type_str:<6} {p.volume:<8.2f} {p.price_open:<12.5f} {p.price_current:<12.5f} {pnl:<10.2f}")
    
    print(f"\nTotal P&L: {total_pnl:.2f}")

def show_orders():
    """Display all pending orders."""
    orders = mt5.orders_get()
    if not orders:
        print("No pending orders")
        return
    
    print(f"\n{'='*80}")
    print(f"PENDING ORDERS: {len(orders)}")
    print(f"{'='*80}")
    print(f"{'Ticket':<10} {'Symbol':<12} {'Type':<15} {'Lots':<8} {'Price':<12} {'SL':<12} {'TP':<12}")
    print("-" * 80)
    
    for o in orders:
        type_names = {
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
        }
        type_str = type_names.get(o.type, str(o.type))
        print(f"{o.ticket:<10} {o.symbol:<12} {type_str:<15} {o.volume_current:<8.2f} {o.price_open:<12.5f} {o.sl:<12.5f} {o.tp:<12.5f}")

def show_account():
    """Display account info."""
    account = mt5.account_info()
    print(f"\n{'='*80}")
    print(f"ACCOUNT INFO")
    print(f"{'='*80}")
    print(f"  Server: {account.server}")
    print(f"  Name: {account.name}")
    print(f"  Balance: {account.balance}")
    print(f"  Equity: {account.equity}")
    print(f"  Margin: {account.margin}")
    print(f"  Free Margin: {account.margin_free}")
    print(f"  Margin Level: {account.margin_level:.2f}%")
    print(f"  Leverage: 1:{account.leverage}")

def show_symbol_info(symbol):
    """Display symbol info."""
    info, actual_symbol = get_symbol_info(symbol)
    if not info:
        print(f"Symbol {symbol} not found")
        return
    
    tick = mt5.symbol_info_tick(actual_symbol)
    
    print(f"\n{'='*80}")
    print(f"SYMBOL: {actual_symbol}")
    print(f"{'='*80}")
    print(f"  Bid: {tick.bid if tick else 'N/A'}")
    print(f"  Ask: {tick.ask if tick else 'N/A'}")
    print(f"  Spread: {info.spread} points")
    print(f"  Digits: {info.digits}")
    print(f"  Point: {info.point}")
    print(f"  Min Lot: {info.volume_min}")
    print(f"  Max Lot: {info.volume_max}")
    print(f"  Lot Step: {info.volume_step}")
    print(f"  Tick Value: {info.trade_tick_value}")
    print(f"  Tick Size: {info.trade_tick_size}")
    print(f"  Swap Long: {info.swap_long}")
    print(f"  Swap Short: {info.swap_short}")
    print(f"  Margin Initial: {info.margin_initial}")

def main():
    print("=" * 80)
    print("MT5 ORDER MANAGER")
    print("=" * 80)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--buy-market", metavar="SYMBOL")
    parser.add_argument("--sell-market", metavar="SYMBOL")
    parser.add_argument("--buy-limit", metavar="SYMBOL")
    parser.add_argument("--sell-limit", metavar="SYMBOL")
    parser.add_argument("--buy-stop", metavar="SYMBOL")
    parser.add_argument("--sell-stop", metavar="SYMBOL")
    parser.add_argument("--buy-stop-limit", metavar="SYMBOL")
    parser.add_argument("--sell-stop-limit", metavar="SYMBOL")
    parser.add_argument("--lots", type=float, default=0.01)
    parser.add_argument("--price", type=float)
    parser.add_argument("--sl", type=float)
    parser.add_argument("--tp", type=float)
    parser.add_argument("--risk", type=float, help="Risk % for auto lot calc")
    parser.add_argument("--sl-pips", type=float, help="SL in pips for auto lot calc")
    parser.add_argument("--filling", default="fok", choices=["fok", "ioc", "return", "boc"])
    parser.add_argument("--time", default="gtc", choices=["gtc", "day", "specified", "specified_day"])
    parser.add_argument("--comment", default="")
    parser.add_argument("--close-ticket", type=int)
    parser.add_argument("--close-symbol", metavar="SYMBOL")
    parser.add_argument("--close-all", action="store_true")
    parser.add_argument("--modify-sl-tp", action="store_true")
    parser.add_argument("--remove-pending", action="store_true")
    parser.add_argument("--positions", action="store_true")
    parser.add_argument("--orders", action="store_true")
    parser.add_argument("--account", action="store_true")
    parser.add_argument("--symbol-info", metavar="SYMBOL")
    parser.add_argument("--ticket", type=int, help="Ticket for modify/remove/close")
    args = parser.parse_args()
    if not init_mt5():
        return
    
    # Execute commands
    if args.account:
        show_account()
    
    if args.positions:
        show_positions()
    
    if args.orders:
        show_orders()
    
    if args.symbol_info:
        show_symbol_info(args.symbol_info)
    
    if args.close_all:
        close_all_positions()
    
    if args.close_symbol:
        positions = mt5.positions_get()
        if positions:
            for p in positions:
                if p.symbol == args.close_symbol:
                    close_position(p.ticket)
    
    if args.ticket:
        if args.modify_sltp:
            modify_sltp(args.ticket, args.sl, args.tp)
        elif args.remove_pending:
            remove_pending_order(args.ticket)
        else:
            close_position(args.ticket)
    
    # Order placement
    order_map = {
        "buy_market": args.buy_market,
        "sell_market": args.sell_market,
        "buy_limit": args.buy_limit,
        "sell_limit": args.sell_limit,
        "buy_stop": args.buy_stop,
        "sell_stop": args.sell_stop,
        "buy_stop_limit": args.buy_stop_limit,
        "sell_stop_limit": args.sell_stop_limit,
    }
    
    for order_type_name, symbol in order_map.items():
        if symbol:
            # Calculate lots if risk specified
            lots = args.lots
            if args.risk and args.sl_pips:
                lots = calculate_lot_size(symbol, args.risk, args.sl_pips)
                print(f"Auto-calculated lots: {lots} (risk={args.risk}%, SL={args.sl_pips} pips)")
            
            # Convert order type name
            type_key = order_type_name.replace("_market", "")
            order_type = ORDER_TYPES.get(type_key)
            
            if order_type is None:
                print(f"Unknown order type: {order_type_name}")
                continue
            
            # For market orders, price is current market
            price = args.price
            if order_type_name in ["buy_market", "sell_market"]:
                info, actual = get_symbol_info(symbol)
                if info:
                    tick = mt5.symbol_info_tick(actual)
                    if tick:
                        price = tick.ask if "buy" in order_type_name else tick.bid
            
            send_order(symbol, order_type, lots, price, args.sl, args.tp,
                      args.filling, args.time, args.comment)
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
