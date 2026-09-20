#!/usr/bin/env python3
"""MT5 PRACTICE ORDER EXECUTION — Actually place the orders."""
import sys
sys.path.insert(0, "C:/Users/victo")
from mt5_order_manager import init_mt5, send_order
import MetaTrader5 as mt5

if not init_mt5():
    sys.exit(1)

account = mt5.account_info()
print(f"Balance: ${account.balance:,.2f}")
print(f"Free Margin: ${account.margin_free:,.2f}")

placed = []

# ============================================================
# ORDER 1: BNBUSD — LIMIT BUY (High Conviction: WR 51.5%)
# Backtest: WR=51.5%, Avg=+1.17%
# ============================================================
print("\n" + "="*60)
print("PLACING: BNBUSD LIMIT BUY (High Conviction)")
print("="*60)
result = send_order("BNBUSD", mt5.ORDER_TYPE_BUY_LIMIT, 
                    lots=0.5, price=750.0, sl=720.0, tp=815.0,
                    comment="HighConv: WR=51.5%, Avg=+1.17%")
if result:
    placed.append(("BNBUSD", "BUY_LIMIT", 750.0, 0.5))

# ============================================================
# ORDER 2: DOGEUSD — LIMIT BUY (Dip Buy: RSI 40)
# Backtest: WR=39.6%, not high conviction but RSI dip
# ============================================================
print("\n" + "="*60)
print("PLACING: DOGEUSD LIMIT BUY (Dip Buy)")
print("="*60)
result = send_order("DOGEUSD", mt5.ORDER_TYPE_BUY_LIMIT,
                    lots=10000, price=0.082, sl=0.078, tp=0.092,
                    comment="DipBuy: RSI=40")
if result:
    placed.append(("DOGEUSD", "BUY_LIMIT", 0.082, 10000))

# ============================================================
# ORDER 3: XRPUSD — LIMIT BUY (Dip Buy: RSI 47)
# Backtest: WR=36%, not high conviction but RSI dip
# ============================================================
print("\n" + "="*60)
print("PLACING: XRPUSD LIMIT BUY (Dip Buy)")
print("="*60)
result = send_order("XRPUSD", mt5.ORDER_TYPE_BUY_LIMIT,
                    lots=500, price=1.35, sl=1.27, tp=1.55,
                    comment="DipBuy: RSI=47")
if result:
    placed.append(("XRPUSD", "BUY_LIMIT", 1.35, 500))

# ============================================================
# ORDER 4: DASHUSD — LIMIT BUY (Highest Conviction: WR 59.6%)
# NOT on MT5 but let's try
# ============================================================
# DASH not available on MT5, skip

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*60)
print("ORDERS PLACED")
print("="*60)
for sym, otype, price, lots in placed:
    print(f"  {sym:<10} {otype:<12} @ ${price}  Lots: {lots}")

print(f"\nTotal: {len(placed)} orders placed")

# Show pending orders
orders = mt5.orders_get()
if orders:
    print(f"\nPending orders: {len(orders)}")
    for o in orders:
        print(f"  Ticket {o.ticket}: {o.symbol} {o.type} @ {o.price_open} lots={o.volume_current}")

mt5.shutdown()
print("\nDone")
