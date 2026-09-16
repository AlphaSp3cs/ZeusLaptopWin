#!/usr/bin/env python3
"""
SEPS - Signal Execution Processing System

Processes pending trading signals from OuroTaurus signal cache,
validates against risk limits, and executes approved trades.

Usage:
    python seps_execution_engine.py --process
    python seps_execution_engine.py --status
    python seps_execution_engine.py --report
"""

import json
import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
SCRIPT_DIR = Path(__file__).parent
LOG_PATH = SCRIPT_DIR / 'seps_execution.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# RISK CONFIGURATION
# ============================================================================

@dataclass
class RiskLimits:
    """Risk management limits for trade execution"""
    max_position_size_pct: float = 2.0      # Max 2% of portfolio per trade
    max_daily_loss_pct: float = 5.0         # Max 5% daily loss
    max_portfolio_exposure_pct: float = 60.0  # Max 60% total exposure
    min_rr_ratio: float = 1.5               # Minimum risk:reward ratio
    min_conviction: int = 4                 # Minimum conviction score (1-5)
    max_correlation_exposure: float = 30.0  # Max exposure to correlated assets
    stop_loss_default_pct: float = 3.0      # Default stop loss if not specified
    
# Default risk limits
DEFAULT_RISK_LIMITS = RiskLimits()

# ============================================================================
# TRADE STATUS ENUMS
# ============================================================================

class TradeStatus(Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"

class RejectionReason(Enum):
    LOW_CONVICTION = "conviction_below_threshold"
    POOR_RR = "risk_reward_insufficient"
    EXCEEDS_POSITION_LIMIT = "exceeds_max_position"
    EXCEEDS_DAILY_LOSS = "exceeds_daily_loss_limit"
    EXCEEDS_PORTFOLIO_EXPOSURE = "exceeds_portfolio_exposure"
    HIGH_CORRELATION = "high_correlation_risk"
    MARKET_HALT = "market_halted"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    ALREADY_POSITIONED = "already_positioned"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Trade:
    """Represents a trade to be executed"""
    trade_id: str
    ticker: str
    signal_type: str  # 'bottom' or 'reversal'
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_pct: float
    conviction: int
    rr_ratio: float
    timestamp: str
    status: str = TradeStatus.PENDING.value
    rejection_reason: Optional[str] = None
    executed_price: Optional[float] = None
    executed_at: Optional[str] = None

@dataclass
class PortfolioState:
    """Current portfolio state for risk checks"""
    total_value: float
    cash_available: float
    current_positions: Dict[str, float]  # ticker -> position value
    daily_pnl: float
    total_exposure_pct: float

# ============================================================================
# DATABASE MANAGEMENT
# ============================================================================

class TradeDatabase:
    """SQLite database for trade tracking and execution history"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize trade database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                position_size_pct REAL NOT NULL,
                conviction INTEGER NOT NULL,
                rr_ratio REAL NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                rejection_reason TEXT,
                executed_price REAL,
                executed_at TEXT,
                notes TEXT
            )
        ''')
        
        # Portfolio snapshot table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_value REAL NOT NULL,
                cash_available REAL NOT NULL,
                total_exposure_pct REAL NOT NULL,
                daily_pnl REAL NOT NULL,
                positions_json TEXT
            )
        ''')
        
        # Execution log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Trade database initialized: {self.db_path}")
    
    def save_trade(self, trade: Trade):
        """Save or update a trade record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trades 
            (trade_id, ticker, signal_type, entry_price, stop_loss, take_profit,
             position_size_pct, conviction, rr_ratio, timestamp, status,
             rejection_reason, executed_price, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.trade_id, trade.ticker, trade.signal_type,
            trade.entry_price, trade.stop_loss, trade.take_profit,
            trade.position_size_pct, trade.conviction, trade.rr_ratio,
            trade.timestamp, trade.status, trade.rejection_reason,
            trade.executed_price, trade.executed_at
        ))
        
        conn.commit()
        conn.close()
    
    def save_portfolio_snapshot(self, portfolio: PortfolioState, positions: Dict):
        """Save portfolio state snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO portfolio_snapshots 
            (timestamp, total_value, cash_available, total_exposure_pct, daily_pnl, positions_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            portfolio.total_value,
            portfolio.cash_available,
            portfolio.total_exposure_pct,
            portfolio.daily_pnl,
            json.dumps(positions)
        ))
        
        conn.commit()
        conn.close()
    
    def log_execution(self, trade_id: str, action: str, details: str):
        """Log execution action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO execution_log (trade_id, action, details, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (trade_id, action, details, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_pending_trades(self) -> List[Dict]:
        """Get all pending trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades WHERE status = ? ORDER BY timestamp DESC
        ''', (TradeStatus.PENDING.value,))
        
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades
    
    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        """Get recent execution history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        history = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return history

# ============================================================================
# SIGNAL PROCESSOR
# ============================================================================

class SignalProcessor:
    """Processes signals from OuroTaurus cache and generates trade candidates"""
    
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
    
    def load_cache(self) -> Optional[Dict]:
        """Load signal cache from JSON file"""
        try:
            with open(self.cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load signal cache: {e}")
            return None
    
    def extract_trade_candidates(self, cache: Dict, risk_limits: RiskLimits) -> List[Trade]:
        """Extract actionable trade candidates from signal cache"""
        candidates = []
        scan_timestamp = cache.get('scan_timestamp', datetime.now().isoformat())
        
        for result in cache.get('scan_results', []):
            ticker = result.get('ticker')
            conviction = result.get('conviction', 0)
            current_price = result.get('current_price', 0)
            
            # Check for bottom signal
            bottom_signal = result.get('bottom_signal')
            if bottom_signal and conviction >= risk_limits.min_conviction:
                entry = bottom_signal.get('entry', current_price)
                stop = bottom_signal.get('sl', current_price * 0.97)
                target = bottom_signal.get('tp', current_price * 1.05)
                rr = bottom_signal.get('rr', 1.0)
                
                if rr >= risk_limits.min_rr_ratio:
                    trade = Trade(
                        trade_id=f"{ticker}_BOTTOM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        ticker=ticker,
                        signal_type='bottom',
                        entry_price=entry,
                        stop_loss=stop,
                        take_profit=target,
                        position_size_pct=risk_limits.max_position_size_pct,
                        conviction=conviction,
                        rr_ratio=rr,
                        timestamp=scan_timestamp
                    )
                    candidates.append(trade)
                    logger.info(f"Bottom signal extracted: {ticker} (conviction: {conviction}, R:R: {rr:.2f})")
            
            # Check for reversal signal
            reversal_signal = result.get('reversal_signal')
            if reversal_signal and conviction >= risk_limits.min_conviction:
                entry = reversal_signal.get('entry', current_price)
                stop = reversal_signal.get('sl', current_price * 0.97)
                target = reversal_signal.get('tp', current_price * 1.05)
                rr = reversal_signal.get('rr', 1.0)
                
                if rr >= risk_limits.min_rr_ratio:
                    trade = Trade(
                        trade_id=f"{ticker}_REVERSAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        ticker=ticker,
                        signal_type='reversal',
                        entry_price=entry,
                        stop_loss=stop,
                        take_profit=target,
                        position_size_pct=risk_limits.max_position_size_pct,
                        conviction=conviction,
                        rr_ratio=rr,
                        timestamp=scan_timestamp
                    )
                    candidates.append(trade)
                    logger.info(f"Reversal signal extracted: {ticker} (conviction: {conviction}, R:R: {rr:.2f})")
        
        return candidates

# ============================================================================
# RISK VALIDATOR
# ============================================================================

class RiskValidator:
    """Validates trades against risk limits"""
    
    def __init__(self, risk_limits: RiskLimits):
        self.limits = risk_limits
    
    def validate_trade(self, trade: Trade, portfolio: PortfolioState) -> Tuple[bool, Optional[RejectionReason]]:
        """
        Validate a trade against all risk limits.
        Returns (is_valid, rejection_reason)
        """
        # Check conviction
        if trade.conviction < self.limits.min_conviction:
            return False, RejectionReason.LOW_CONVICTION
        
        # Check R:R ratio
        if trade.rr_ratio < self.limits.min_rr_ratio:
            return False, RejectionReason.POOR_RR
        
        # Check position size limit
        if trade.position_size_pct > self.limits.max_position_size_pct:
            return False, RejectionReason.EXCEEDS_POSITION_LIMIT
        
        # Check portfolio exposure
        new_exposure = portfolio.total_exposure_pct + trade.position_size_pct
        if new_exposure > self.limits.max_portfolio_exposure_pct:
            return False, RejectionReason.EXCEEDS_PORTFOLIO_EXPOSURE
        
        # Check daily loss limit
        if portfolio.daily_pnl < 0:
            loss_pct = abs(portfolio.daily_pnl) / portfolio.total_value * 100
            if loss_pct >= self.limits.max_daily_loss_pct:
                return False, RejectionReason.EXCEEDS_DAILY_LOSS
        
        # Check for existing position (simple check)
        if trade.ticker in portfolio.current_positions:
            existing_size = portfolio.current_positions[trade.ticker]
            if existing_size > 0:
                return False, RejectionReason.ALREADY_POSITIONED
        
        # All checks passed
        return True, None
    
    def validate_batch(self, trades: List[Trade], portfolio: PortfolioState) -> List[Trade]:
        """Validate a batch of trades and return approved ones"""
        approved = []
        
        for trade in trades:
            is_valid, rejection_reason = self.validate_trade(trade, portfolio)
            
            if is_valid:
                trade.status = TradeStatus.APPROVED.value
                approved.append(trade)
                
                # Update running exposure for next trade check
                portfolio.total_exposure_pct += trade.position_size_pct
            else:
                trade.status = TradeStatus.REJECTED.value
                trade.rejection_reason = rejection_reason.value if rejection_reason else "unknown"
        
        return approved

# ============================================================================
# TRADE EXECUTOR
# ============================================================================

class TradeExecutor:
    """Executes approved trades (simulated or live)"""
    
    def __init__(self, db: TradeDatabase, simulation_mode: bool = True):
        self.db = db
        self.simulation_mode = simulation_mode
        self.executed_trades = []
    
    def execute_trade(self, trade: Trade) -> bool:
        """Execute a single trade"""
        if trade.status != TradeStatus.APPROVED.value:
            logger.warning(f"Trade {trade.trade_id} not approved for execution")
            return False
        
        try:
            if self.simulation_mode:
                # Simulated execution
                executed_price = trade.entry_price * (1 + (hash(trade.trade_id) % 100) / 10000)  # Small slippage
                logger.info(f"[SIMULATED] Executing {trade.ticker} {trade.signal_type} @ ${executed_price:.4f}")
            else:
                # Live execution would go here (API calls to exchange)
                executed_price = trade.entry_price
                logger.info(f"[LIVE] Executing {trade.ticker} {trade.signal_type} @ ${executed_price:.4f}")
            
            # Update trade record
            trade.status = TradeStatus.EXECUTED.value
            trade.executed_price = executed_price
            trade.executed_at = datetime.now().isoformat()
            trade.notes = "Simulated execution" if self.simulation_mode else "Live execution"
            
            # Save to database
            self.db.save_trade(trade)
            self.db.log_execution(
                trade.trade_id,
                "EXECUTE",
                f"Executed {trade.ticker} @ ${executed_price:.4f}, size: {trade.position_size_pct}%"
            )
            
            self.executed_trades.append(trade)
            return True
            
        except Exception as e:
            logger.error(f"Execution failed for {trade.trade_id}: {e}")
            trade.status = TradeStatus.CANCELLED.value
            trade.rejection_reason = f"execution_error: {str(e)}"
            self.db.save_trade(trade)
            self.db.log_execution(trade.trade_id, "CANCELLED", str(e))
            return False
    
    def execute_batch(self, trades: List[Trade]) -> Dict:
        """Execute a batch of approved trades"""
        results = {
            'total': len(trades),
            'executed': 0,
            'failed': 0,
            'trades': []
        }
        
        for trade in trades:
            success = self.execute_trade(trade)
            if success:
                results['executed'] += 1
            else:
                results['failed'] += 1
            results['trades'].append({
                'trade_id': trade.trade_id,
                'ticker': trade.ticker,
                'status': trade.status,
                'executed_price': trade.executed_price
            })
        
        return results

# ============================================================================
# SEPS ENGINE
# ============================================================================

class SEPS_Engine:
    """Main SEPS execution engine"""
    
    def __init__(self, 
                 cache_path: Path = SCRIPT_DIR / 'ourotaurus_signal_cache.json',
                 db_path: Path = SCRIPT_DIR / 'seps_trades.db',
                 risk_limits: RiskLimits = DEFAULT_RISK_LIMITS,
                 simulation_mode: bool = True):
        
        self.cache_path = cache_path
        self.risk_limits = risk_limits
        self.simulation_mode = simulation_mode
        
        # Initialize components
        self.db = TradeDatabase(db_path)
        self.signal_processor = SignalProcessor(cache_path)
        self.risk_validator = RiskValidator(risk_limits)
        self.executor = TradeExecutor(self.db, simulation_mode)
        
        # Portfolio state (in production, this would be fetched from broker)
        self.portfolio = PortfolioState(
            total_value=100000.0,  # $100k default
            cash_available=70000.0,  # 70% cash
            current_positions={},
            daily_pnl=0.0,
            total_exposure_pct=30.0
        )
    
    def run_cycle(self) -> Dict:
        """Run a complete SEPS cycle"""
        cycle_start = datetime.now()
        logger.info("=" * 70)
        logger.info(f"SEPS CYCLE STARTED - {cycle_start.isoformat()}")
        logger.info("=" * 70)
        
        results = {
            'cycle_start': cycle_start.isoformat(),
            'signals_processed': 0,
            'trades_approved': 0,
            'trades_executed': 0,
            'trades_rejected': 0,
            'execution_details': []
        }
        
        # Step 1: Load signal cache
        logger.info("Step 1: Loading signal cache...")
        cache = self.signal_processor.load_cache()
        
        if not cache:
            logger.error("Failed to load signal cache - aborting cycle")
            results['error'] = "cache_load_failed"
            return results
        
        scan_timestamp = cache.get('scan_timestamp', 'unknown')
        logger.info(f"Loaded cache from scan: {scan_timestamp}")
        
        # Step 2: Extract trade candidates
        logger.info("Step 2: Extracting trade candidates from signals...")
        candidates = self.signal_processor.extract_trade_candidates(cache, self.risk_limits)
        results['signals_processed'] = len(candidates)
        
        if not candidates:
            logger.info("No actionable trade candidates found in current signals")
            results['message'] = "No actionable signals"
        else:
            logger.info(f"Found {len(candidates)} trade candidates")
        
        # Step 3: Risk validation
        logger.info("Step 3: Validating trades against risk limits...")
        approved_trades = self.risk_validator.validate_batch(candidates, self.portfolio)
        
        rejected = [t for t in candidates if t.status == TradeStatus.REJECTED.value]
        results['trades_approved'] = len(approved_trades)
        results['trades_rejected'] = len(rejected)
        
        logger.info(f"Validated: {len(approved_trades)} approved, {len(rejected)} rejected")
        
        # Save all trades to DB
        for trade in candidates:
            self.db.save_trade(trade)
            if trade.status == TradeStatus.REJECTED.value:
                self.db.log_execution(
                    trade.trade_id, 
                    "REJECTED", 
                    f"Reason: {trade.rejection_reason}"
                )
        
        # Step 4: Execute approved trades
        if approved_trades:
            logger.info("Step 4: Executing approved trades...")
            exec_results = self.executor.execute_batch(approved_trades)
            results['trades_executed'] = exec_results['executed']
            results['execution_details'] = exec_results['trades']
            
            logger.info(f"Execution complete: {exec_results['executed']}/{exec_results['total']} executed")
        else:
            logger.info("Step 4: No trades to execute")
        
        # Step 5: Save portfolio snapshot
        self.db.save_portfolio_snapshot(self.portfolio, self.portfolio.current_positions)
        
        # Cycle summary
        cycle_end = datetime.now()
        cycle_duration = (cycle_end - cycle_start).total_seconds()
        
        logger.info("=" * 70)
        logger.info(f"SEPS CYCLE COMPLETE - Duration: {cycle_duration:.2f}s")
        logger.info(f"  Signals Processed: {results['signals_processed']}")
        logger.info(f"  Trades Approved:   {results['trades_approved']}")
        logger.info(f"  Trades Executed:   {results['trades_executed']}")
        logger.info(f"  Trades Rejected:   {results['trades_rejected']}")
        logger.info(f"  Mode: {'SIMULATION' if self.simulation_mode else 'LIVE'}")
        logger.info("=" * 70)
        
        results['cycle_end'] = cycle_end.isoformat()
        results['duration_seconds'] = cycle_duration
        results['mode'] = 'simulation' if self.simulation_mode else 'live'
        
        return results
    
    def get_status(self) -> Dict:
        """Get current SEPS status"""
        pending = self.db.get_pending_trades()
        history = self.db.get_execution_history(20)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'simulation_mode': self.simulation_mode,
            'risk_limits': asdict(self.risk_limits),
            'portfolio': asdict(self.portfolio),
            'pending_trades': len(pending),
            'recent_executions': history
        }
    
    def generate_report(self) -> str:
        """Generate human-readable execution report"""
        status = self.get_status()
        history = status['recent_executions']
        
        lines = []
        lines.append("=" * 70)
        lines.append("SEPS - SIGNAL EXECUTION PROCESSING SYSTEM")
        lines.append("Execution Report")
        lines.append("=" * 70)
        lines.append(f"Generated: {status['timestamp']}")
        lines.append(f"Mode: {status['simulation_mode']}")
        lines.append("")
        
        lines.append("RISK LIMITS:")
        lines.append(f"  Max Position Size: {self.risk_limits.max_position_size_pct}%")
        lines.append(f"  Max Daily Loss: {self.risk_limits.max_daily_loss_pct}%")
        lines.append(f"  Max Portfolio Exposure: {self.risk_limits.max_portfolio_exposure_pct}%")
        lines.append(f"  Min R:R Ratio: {self.risk_limits.min_rr_ratio}")
        lines.append(f"  Min Conviction: {self.risk_limits.min_conviction}/5")
        lines.append("")
        
        lines.append("PORTFOLIO STATE:")
        lines.append(f"  Total Value: ${self.portfolio.total_value:,.2f}")
        lines.append(f"  Cash Available: ${self.portfolio.cash_available:,.2f}")
        lines.append(f"  Current Exposure: {self.portfolio.total_exposure_pct}%")
        lines.append(f"  Daily P&L: ${self.portfolio.daily_pnl:,.2f}")
        lines.append("")
        
        if history:
            lines.append("RECENT EXECUTIONS:")
            lines.append("-" * 70)
            for entry in history[:10]:
                lines.append(f"  [{entry['timestamp'][:19]}] {entry['action']}: {entry['details']}")
        else:
            lines.append("No recent executions")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='SEPS - Signal Execution Processing System')
    parser.add_argument('--process', '-p', action='store_true',
                       help='Run a complete SEPS cycle')
    parser.add_argument('--status', '-s', action='store_true',
                       help='Show current SEPS status')
    parser.add_argument('--report', '-r', action='store_true',
                       help='Generate execution report')
    parser.add_argument('--live', '-l', action='store_true',
                       help='Run in live mode (not simulation)')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Output as JSON')
    
    args = parser.parse_args()
    
    # Initialize SEPS engine
    seps = SEPS_Engine(simulation_mode=not args.live)
    
    if args.process:
        results = seps.run_cycle()
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print(f"\nSEPS Cycle Complete:")
            print(f"  Signals Processed: {results.get('signals_processed', 0)}")
            print(f"  Trades Approved: {results.get('trades_approved', 0)}")
            print(f"  Trades Executed: {results.get('trades_executed', 0)}")
            print(f"  Trades Rejected: {results.get('trades_rejected', 0)}")
            if results.get('execution_details'):
                print("\nExecuted Trades:")
                for t in results['execution_details']:
                    print(f"  - {t['ticker']}: {t['status']} @ ${t.get('executed_price', 'N/A')}")
    
    elif args.status:
        status = seps.get_status()
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            print(seps.generate_report())
    
    elif args.report:
        print(seps.generate_report())
    
    else:
        # Default: run cycle
        results = seps.run_cycle()
        print(seps.generate_report())

if __name__ == '__main__':
    main()