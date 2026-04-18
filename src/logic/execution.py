import logging
import time
import json
from src.database import Database

class ExecutionManager:
    def __init__(self, db, exchange):
        self.db = db
        self.exchange = exchange
        self.trading_fee_percentage = 0.06 # MEXC Futures Fee approx
        self.paper_mode = False
        self.leverage = 20
        self._load_config()

        # Paper Wallet State
        self.paper_balance = {"USDT": 1000.0}
        self.paper_positions = {} # Key: Ticker -> {amount, entry_price, side, margin, leverage}

        if self.paper_mode:
            logging.info("ExecutionManager starting in PAPER mode")
            self._load_paper_state()

    def _load_config(self):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.trading_fee_percentage = config.get('trading', {}).get('fee_percentage', 0.06)
                self.paper_mode = (config.get('trading', {}).get('mode', 'LIVE') == 'PAPER')
                self.leverage = config.get('trading', {}).get('leverage', 20)
        except Exception as e:
            logging.warning(f"Failed to load fee config: {e}. Using default")

    def _load_paper_state(self):
        """Loads paper wallet state from DB."""
        try:
            # Load USDT and Longs from wallet_balances
            rows = self.db.query("SELECT currency, amount FROM wallet_balances")
            for r in rows:
                curr, amt = r
                self.paper_balance[curr] = float(amt)

            if "USDT" not in self.paper_balance:
                self.paper_balance["USDT"] = 1000.0
                self._save_paper_balance("USDT", 1000.0)

            # Load ALL positions for Internal Logic
            rows_all = self.db.query("SELECT value FROM system_status WHERE key = 'paper_all_positions'")
            if rows_all:
                self.paper_positions = json.loads(rows_all[0][0])

        except Exception as e:
            logging.error(f"Failed to load paper state: {e}")

    def _save_paper_state(self):
        try:
            # 1. Save USDT and Longs to wallet_balances
            for curr, amt in self.paper_balance.items():
                self.db.execute("INSERT INTO wallet_balances (currency, amount) VALUES (%s, %s) ON CONFLICT (currency) DO UPDATE SET amount = EXCLUDED.amount", (curr, amt))

            # Also clean up 0 balances
            for curr in list(self.paper_balance.keys()):
                if self.paper_balance[curr] <= 0.00001:
                     self.db.execute("DELETE FROM wallet_balances WHERE currency = %s", (curr,))

            # 2. Save Shorts for Dashboard (Format expected: Ticker_SHORT)
            shorts_for_dash = {}
            for ticker, pos in self.paper_positions.items():
                if pos['side'] == 'SHORT':
                    key = f"{ticker}_SHORT"
                    shorts_for_dash[key] = {
                        "entry_price": pos['entry_price'],
                        "margin_usdt": pos['margin'],
                        "amount_coins": pos['amount'],
                        "leverage": pos['leverage']
                    }

            self.db.execute("INSERT INTO system_status (key, value, updated_at) VALUES (%s, %s, NOW()) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
                            ("paper_short_positions", json.dumps(shorts_for_dash)))

            # 3. Save ALL positions for Internal Logic
            self.db.execute("INSERT INTO system_status (key, value, updated_at) VALUES (%s, %s, NOW()) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
                            ("paper_all_positions", json.dumps(self.paper_positions)))

        except Exception as e:
            logging.error(f"Failed to save paper state: {e}")

    def _save_paper_balance(self, curr, amt):
        self.db.execute("INSERT INTO wallet_balances (currency, amount) VALUES (%s, %s) ON CONFLICT (currency) DO UPDATE SET amount = EXCLUDED.amount", (curr, amt))

    def set_leverage(self, symbol, leverage=20):
        if self.paper_mode:
            self.leverage = leverage
            return True

        if not self.exchange:
            logging.error("No exchange instance for set_leverage")
            return False

        try:
            self.exchange.set_leverage(leverage, symbol)
            logging.info(f"Leverage set to {leverage}x for {symbol}")
            return True
        except Exception as e:
            logging.error(f"Failed to set leverage: {e}")
            return False

    def set_margin_mode(self, symbol, mode='isolated'):
        if self.paper_mode:
            return True

        if not self.exchange:
            return False

        try:
            self.exchange.set_margin_mode(mode, symbol)
            logging.info(f"Margin mode set to {mode} for {symbol}")
            return True
        except Exception as e:
            logging.error(f"Failed to set margin mode: {e}")
            return False

    def get_position(self, symbol):
        if self.paper_mode:
            pos = self.paper_positions.get(symbol)
            if not pos:
                return 0.0
            size = pos['amount']
            if pos['side'] == 'SHORT':
                size = -size
            return size

        if not self.exchange:
            return 0.0

        try:
            positions = self.exchange.fetch_positions([symbol])
            if not positions:
                positions = self.exchange.fetch_positions()

            base_symbol = symbol.split(':')[0] if ':' in symbol else symbol

            for pos in positions:
                pos_sym = pos['symbol']
                pos_base = pos_sym.split(':')[0] if ':' in pos_sym else pos_sym

                if pos_base == base_symbol:
                    side = pos['side']
                    size = float(pos['contracts'])

                    if side == 'long':
                        return size
                    elif side == 'short':
                        return -size
            return 0.0
        except Exception as e:
            logging.error(f"Error fetching position: {e}")
            return 0.0

    def get_balance(self, currency='USDT'):
        if self.paper_mode:
            return self.paper_balance.get(currency, 0.0)
        else:
            try:
                bal = self.exchange.fetch_balance()
                return float(bal[currency]['free'])
            except:
                return 0.0

    def calculate_dynamic_sl(self, price, atr, mode, leverage=20):
        if mode == 'TREND':
            sl_dist = 2.0 * atr
        else:
            sl_dist = 1.0 * atr

        return float(sl_dist)

    def execute_order(self, action, ticker, amount, price=None, params={}):
        if self.paper_mode:
            return self._simulate_order(action, ticker, amount, price)
        else:
            return self._execute_real_order(action, ticker, amount, price, params)

    def _simulate_order(self, action, ticker, amount, price=None):
        if not price:
             try:
                 ticker_data = self.exchange.fetch_ticker(ticker)
                 price = float(ticker_data['last'])
             except:
                 logging.error("Could not fetch price for simulation")
                 return False

        current_pos = self.paper_positions.get(ticker)
        usdt_bal = self.paper_balance.get("USDT", 0.0)

        trade_val = amount * price
        fee = trade_val * (self.trading_fee_percentage / 100.0)
        cost = trade_val / self.leverage

        logging.info(f"[PAPER] Req: {action} {amount} @ {price} | Cost: {cost:.2f} | Fee: {fee:.4f} | Bal: {usdt_bal:.2f}")

        if action in ['LONG', 'SHORT']:
            if usdt_bal < (cost + fee):
                logging.warning(f"Insufficient paper funds: Need {cost+fee}, have {usdt_bal}")
                return False

            self.paper_balance["USDT"] -= (cost + fee)

            if not current_pos:
                self.paper_positions[ticker] = {
                    'side': action,
                    'amount': amount,
                    'entry_price': price,
                    'margin': cost,
                    'leverage': self.leverage
                }
            else:
                if current_pos['side'] != action:
                    logging.error("Simulated flip without close not supported directly")
                    return False
                # Average Entry
                total_amt = current_pos['amount'] + amount
                avg_entry = ((current_pos['amount'] * current_pos['entry_price']) + (amount * price)) / total_amt
                current_pos['amount'] = total_amt
                current_pos['entry_price'] = avg_entry
                current_pos['margin'] += cost

            if action == 'LONG':
                base_curr = ticker.split('/')[0]
                self.paper_balance[base_curr] = self.paper_positions[ticker]['amount']

        elif action in ['CLOSE_LONG', 'CLOSE_SHORT']:
             if not current_pos:
                 return False

             side = 'LONG' if action == 'CLOSE_LONG' else 'SHORT'
             if current_pos['side'] != side:
                 return False

             close_amt = min(amount, current_pos['amount'])

             # PnL Calc
             if side == 'LONG':
                 pnl = (price - current_pos['entry_price']) * close_amt
             else:
                 pnl = (current_pos['entry_price'] - price) * close_amt

             # Margin Release
             margin_release = (close_amt * current_pos['entry_price']) / self.leverage

             total_return = margin_release + pnl - fee
             self.paper_balance["USDT"] += total_return

             logging.info(f"[PAPER] Closed {side}. PnL: {pnl:.2f}, Ret: {total_return:.2f}")

             current_pos['amount'] -= close_amt
             current_pos['margin'] -= margin_release

             if current_pos['amount'] <= 0.00001:
                 del self.paper_positions[ticker]
                 if side == 'LONG':
                     base_curr = ticker.split('/')[0]
                     if base_curr in self.paper_balance:
                         del self.paper_balance[base_curr]

        # Calculate actual pnl
        trade_pnl = pnl if action in ['CLOSE_LONG', 'CLOSE_SHORT'] else 0.0

        # Log Trade
        self._log_trade_to_db(action, ticker, amount, {
            'price': price,
            'cost': cost if action in ['LONG', 'SHORT'] else 0,
            'fee': {'cost': fee},
            'average': price
        }, pnl=trade_pnl)

        self._save_paper_state()
        return True

    def _execute_real_order(self, action, ticker, amount, price=None, params={}):
        if not self.exchange:
            logging.error("Exchange not connected.")
            return False

        try:
            symbol = ticker
            side = None
            type = 'limit'

            # Map Actions
            if action == 'LONG':
                side = 'buy'
                type = 'limit'
                params['postOnly'] = True
            elif action == 'SHORT':
                side = 'sell'
                type = 'limit'
                params['postOnly'] = True
            elif action in ['CLOSE_LONG', 'CLOSE_SHORT']:
                # WYJŚCIE AWARYJNE (Take Profit lub Stop Loss)
                side = 'sell' if action == 'CLOSE_LONG' else 'buy'
                type = 'market' # Uciekamy agresywnie, poślizg wliczony w EV
                params['reduceOnly'] = True
                if 'postOnly' in params:
                    del params['postOnly'] # ABSOLUTNIE NIE Maker na ucieczce

            if not side:
                logging.error(f"Unknown action: {action}")
                return False

            if type == 'limit':
                if price is None:
                    try:
                        ticker_data = self.exchange.fetch_ticker(symbol)
                        if side == 'buy':
                            price = float(ticker_data['bid'])
                        else:
                            price = float(ticker_data['ask'])
                    except Exception as e:
                        logging.error(f"Failed to fetch ticker for limit price: {e}")
                        return False
            else:
                price = None # Brak określonej ceny dla zleceń market (uciekamy bez limitu)

            logging.info(f"Sending Order: {side.upper()} {amount} {symbol} ({type}) @ {price}")

            # Wykonanie zlecenia
            order = self.exchange.create_order(symbol, type, side, amount, price, params)

            # Log to DB
            self._log_trade_to_db(action, ticker, amount, order)
            
            # --- SMART CHASE LOGIC (Tylko dla wejść z Limitem) ---
            if type == 'limit' and action in ['LONG', 'SHORT']:
                self._chase_order_if_needed(order, action, symbol, side, amount, price, params)
            # ----------------------------------------------------

            return True

        except Exception as e:
            logging.error(f"Order Execution Failed: {e}")
            return False

    def _chase_order_if_needed(self, order, action, symbol, side, amount, original_price, params):
        """
        SMART CHASE: Wait 30 seconds for the Limit Post-Only order to fill. 
        If not filled, cancel it and replace it with a slippage tolerance of 0.05%.
        """
        import threading
        
        def chase_task():
            try:
                order_id = order['id']
                logging.info(f"Smart Chase: Monitoring order {order_id} for 30s...")
                
                # Czekamy 30 sekund
                time.sleep(30)
                
                # Sprawdzamy status zlecenia
                fetched_order = self.exchange.fetch_order(order_id, symbol)
                status = fetched_order['status']
                
                if status == 'open':
                    logging.info(f"Smart Chase: Order {order_id} not filled. Canceling and replacing with 0.05% slippage allowance.")
                    
                    # Anuluj oryginalne zlecenie
                    self.exchange.cancel_order(order_id, symbol)
                    
                    # Czekaj na przetworzenie anulowania
                    time.sleep(1)
                    
                    # Oblicz nową cenę z poślizgiem 0.05%
                    slippage_tolerance = 0.0005
                    
                    if side == 'buy':
                        # Chcemy kupić trochę drożej (wchodząc głębiej w orderbook)
                        new_price = original_price * (1 + slippage_tolerance)
                    else:
                        # Chcemy sprzedać trochę taniej (wchodząc głębiej w orderbook)
                        new_price = original_price * (1 - slippage_tolerance)
                        
                    # Formatuj cenę do poprawnego tick size (użyjemy formatu z giełdy, domyślnie round)
                    try:
                        new_price = float(self.exchange.price_to_precision(symbol, new_price))
                    except:
                        new_price = round(new_price, 6) # Fallback
                        
                    # Upewniamy się, że to nadal Maker, ale nie możemy używać Post-Only z gorszą ceną
                    # bo PostOnly odrzuci zlecenie, jeśli miałoby wejść od razu. 
                    # Smart Chase usuwa Post-Only, żeby wejść "prawie rynkowo" z twardym limitem ceny.
                    chase_params = params.copy()
                    if 'postOnly' in chase_params:
                        del chase_params['postOnly']
                        
                    logging.info(f"Smart Chase: Re-Sending {side.upper()} {amount} {symbol} (limit) @ {new_price} (no post-only)")
                    chase_order = self.exchange.create_order(symbol, 'limit', side, amount, new_price, chase_params)
                    
                    self._log_trade_to_db(action + "_CHASE", symbol, amount, chase_order)
                else:
                    logging.info(f"Smart Chase: Order {order_id} already filled or closed ({status}).")
            except Exception as e:
                logging.error(f"Smart Chase Error: {e}")

        # Start monitoring in a background thread so we don't block the main trader loop
        chase_thread = threading.Thread(target=chase_task)
        chase_thread.daemon = True
        chase_thread.start()

    def _log_trade_to_db(self, action, ticker, amount, order_data, pnl=0.0):
        try:
            price = float(order_data.get('price', 0) or order_data.get('average', 0) or 0)
            cost = float(order_data.get('cost', 0) or 0)
            fee = float(order_data.get('fee', {}).get('cost', 0) or 0)

            self.db.execute("""
                INSERT INTO trades (timestamp, action, ticker, price, amount, cost, fee, pnl, strategy, notes, raw_data)
                VALUES (NOW(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (action, ticker, price, amount, cost, fee, pnl, 'FUTURES' if not self.paper_mode else 'PAPER', '', json.dumps(order_data)))
        except Exception as e:
            logging.error(f"DB Log Error: {e}")

    def update_pnl(self, ticker, current_price):
        """Checks for liquidation and updates PnL."""
        if not self.paper_mode:
            return

        if ticker not in self.paper_positions:
            return

        pos = self.paper_positions[ticker]
        liq_threshold = 1.0 / pos['leverage'] # e.g. 0.05

        liquidated = False

        if pos['side'] == 'LONG':
            # Drop > 5%
            drawdown = (pos['entry_price'] - current_price) / pos['entry_price']
            if drawdown >= liq_threshold:
                liquidated = True
        elif pos['side'] == 'SHORT':
            # Rise > 5%
            drawdown = (current_price - pos['entry_price']) / pos['entry_price']
            if drawdown >= liq_threshold:
                liquidated = True

        if liquidated:
            logging.warning(f"LIQUIDATION on {ticker}!")
            # Loss of margin
            del self.paper_positions[ticker]

            # If Long, remove from mirror
            if pos['side'] == 'LONG':
                 base_curr = ticker.split('/')[0]
                 if base_curr in self.paper_balance:
                     del self.paper_balance[base_curr]

            self._save_paper_state()
            self._log_trade_to_db("LIQUIDATION", ticker, pos['amount'], {'price': current_price, 'fee': {'cost': 0}})
