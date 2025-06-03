from flask import Flask, render_template, request, jsonify
import requests # Make sure this is imported if not already via the main script part
import json # For potential direct use, though jsonify handles most cases
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from collections import deque, defaultdict

# --- Configuration (Keep these at the top) ---
BSCSCAN_API_URL = "https://api.bscscan.com/api"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
BEP20_TRANSFER_EVENT_SIGNATURE = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
API_CALL_DELAY = 0.25
TOKEN_INFO_API_DELAY = 0.2
COINGECKO_API_DELAY = 1

ZKJ_ADDRESS = "0xc71b5f6313554be6853efe9c3ab6b9590f8302e81"
WBNB_ADDRESS = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
USDT_ADDRESS = "0x55d398326f99059ff775485246999027b3197955"
BUSD_ADDRESS = "0xe9e7cea3dedca5984780bafc599bd69add087d56"
QUOTE_TOKEN_ADDRESSES = [WBNB_ADDRESS, USDT_ADDRESS, BUSD_ADDRESS]
BEIJING_TIMEZONE_OFFSET = timedelta(hours=8)

# Global caches (cleared on app restart - for a more persistent cache, use Redis, etc.)
token_info_cache = {}
bnb_price_cache = {}

app = Flask(__name__)

# --- Helper Functions (Copied from your script, ensure they are defined here or imported) ---
def get_utc_from_beijing_time(dt_beijing):
    return dt_beijing - BEIJING_TIMEZONE_OFFSET

def get_beijing_time_from_utc(dt_utc):
    return dt_utc + BEIJING_TIMEZONE_OFFSET

def hex_to_int(hex_string):
    try: return int(hex_string, 16)
    except: return None

def decode_address_from_topic(topic):
    if not topic or len(topic) < 64: return None
    return "0x" + topic[-40:]

def make_api_request_server(url, params, current_bsc_api_key, source="BscScan", is_proxied_block_request=False):
    # Modified to use passed API key
    if source == "BscScan" and 'apikey' not in params:
        params['apikey'] = current_bsc_api_key

    try:
        # print(f"Backend Requesting ({source}): {url} with params keys: {list(params.keys())}")
        response = requests.get(url, params=params, timeout=45)
        response.raise_for_status()
        data = response.json()

        if source == "BscScan":
            if is_proxied_block_request and isinstance(data.get("result"), str) and data.get("result") is None:
                 return None
            if isinstance(data, dict) and data.get("status") == "0":
                # print(f"  BscScan API Error ({params.get('action', params.get('module'))}): {data.get('message')} - {data.get('result')}")
                # Instead of printing, we might want to raise an exception or return an error structure
                raise Exception(f"BscScan API Error: {data.get('message')} - {data.get('result')}")
            return data.get("result") if "result" in data else data
        return data
    except requests.exceptions.HTTPError as e:
        # print(f"  HTTP error ({source}) for {params.get('action', params.get('module'))}: {e}, Response: {response.text if 'response' in locals() else 'N/A'}")
        raise Exception(f"HTTP error for {source}: {e} (Status: {e.response.status_code if e.response else 'N/A'})")
    except requests.exceptions.RequestException as e:
        # print(f"  Request error ({source}): {e}")
        raise Exception(f"Request error for {source}: {e}")
    except json.JSONDecodeError as e:
        # print(f"  JSON decode error ({source}), Response: {response.text if 'response' in locals() else 'N/A'}: {e}")
        raise Exception(f"JSON decode error for {source}: {e}")
    # Removed return None from general exceptions to ensure errors are propagated

def get_token_info_server(token_address, current_bsc_api_key):
    # Modified to use passed API key and global cache
    global token_info_cache
    token_address_lower = token_address.lower()

    if token_address_lower == ZKJ_ADDRESS:
        return {"name": "ZKJ", "symbol": "ZKJ", "decimals": 18}
    if token_address_lower in token_info_cache:
        return token_info_cache[token_address_lower]

    # print(f"    Backend: Fetching token info for: {token_address_lower}...")
    time.sleep(TOKEN_INFO_API_DELAY) # Still respect delay
    info = {}
    # Prioritize known tokens to avoid unnecessary API calls or if BscScan API for general token info is unreliable
    if token_address_lower == WBNB_ADDRESS: info = {"name": "Wrapped BNB", "symbol": "WBNB", "decimals": 18}
    elif token_address_lower == USDT_ADDRESS: info = {"name": "Tether USD", "symbol": "USDT", "decimals": 18}
    elif token_address_lower == BUSD_ADDRESS: info = {"name": "BUSD Token", "symbol": "BUSD", "decimals": 18}
    else:
        # Attempt BscScan API (Note: free tier might not have a reliable generic token info endpoint)
        # For simplicity, this example relies on the pre-defined list or placeholders.
        # A real app might try 'action=token' with 'contractaddress' or other PRO endpoints if available.
        # As 'tokensupply' doesn't reliably give name/symbol for all, we'll use placeholders.
        print(f"    Token info for {token_address_lower} not pre-defined. Using placeholders on server.")
        info = {"name": f"Token ({token_address_lower[-4:]})", "symbol": f"TKN-{token_address_lower[-4:]}", "decimals": 18}

    token_info_cache[token_address_lower] = info
    return info


def get_historical_bnb_price_server(date_str_ddmmyyyy):
    # Uses global cache
    global bnb_price_cache
    if not date_str_ddmmyyyy: return None
    if date_str_ddmmyyyy in bnb_price_cache:
        return bnb_price_cache[date_str_ddmmyyyy]

    # print(f"    Backend: Fetching BNB price for date: {date_str_ddmmyyyy} from CoinGecko...")
    url = f"{COINGECKO_API_URL}/coins/binancecoin/history"
    params = {"date": date_str_ddmmyyyy, "localization": "false"}
    # CoinGecko doesn't need the user's BscScan API key
    data = make_api_request_server(url, params, current_bsc_api_key=None, source="CoinGecko") # No BscScan key needed
    time.sleep(COINGECKO_API_DELAY)

    if data and data.get("market_data", {}).get("current_price", {}).get("usd") is not None:
        price = data["market_data"]["current_price"]["usd"]
        bnb_price_cache[date_str_ddmmyyyy] = price
        # print(f"      BNB price on {date_str_ddmmyyyy}: ${price:.2f}")
        return price
    else:
        # print(f"      Could not fetch BNB price for {date_str_ddmmyyyy}.")
        bnb_price_cache[date_str_ddmmyyyy] = None
        return None

def get_block_number_by_timestamp_bsc_server(timestamp_utc_unix, closest_option, current_bsc_api_key):
    # print(f"  Backend: Fetching block for ts {timestamp_utc_unix}, closest={closest_option}...")
    params = {
        "module": "block", "action": "getblocknobytime",
        "timestamp": timestamp_utc_unix, "closest": closest_option
    }
    result = make_api_request_server(BSCSCAN_API_URL, params, current_bsc_api_key)
    time.sleep(API_CALL_DELAY)
    if result and isinstance(result, str) and result.isdigit():
        return int(result)
    # print(f"    Backend: Could not fetch block for ts {timestamp_utc_unix}. Result: {result}")
    return None


def fetch_wallet_transactions_by_blockrange_server(wallet_address, start_block, end_block, current_bsc_api_key):
    # print(f"\nBackend: Fetching txs for {wallet_address} from block {start_block} to {end_block}...")
    all_txs_in_range = []
    current_page = 1
    max_offset = 1000 # Max 10000, but 1000 is safer for multiple pages
    
    while True:
        # print(f"  Backend: Fetching page {current_page}...")
        params = {
            "module": "account", "action": "txlist", "address": wallet_address,
            "startblock": start_block, "endblock": end_block,
            "page": current_page, "offset": max_offset, "sort": "asc",
        }
        transactions_page = make_api_request_server(BSCSCAN_API_URL, params, current_bsc_api_key)
        time.sleep(API_CALL_DELAY)

        if transactions_page and isinstance(transactions_page, list):
            all_txs_in_range.extend(transactions_page)
            if len(transactions_page) < max_offset: break
            current_page += 1
        elif isinstance(transactions_page, list) and not transactions_page: break # Empty list
        else:
            # print(f"  Backend: Error fetching page {current_page} or no more txs.")
            raise Exception(f"Failed to fetch transactions page {current_page} for wallet {wallet_address}") # Propagate error
        if current_page > 20: # Safety break
            # print("  Backend: Reached max page limit (20).")
            break
    return all_txs_in_range

def get_bep20_transfers_and_classify_server(tx_hash, wallet_address_main, tx_date_for_price, tx_timestamp_unix, current_bsc_api_key):
    # print(f"    Backend: Processing Tx Receipt: {tx_hash}...")
    params_tx_receipt = {"module": "proxy", "action": "eth_getTransactionReceipt", "txhash": tx_hash}
    receipt_data = make_api_request_server(BSCSCAN_API_URL, params_tx_receipt, current_bsc_api_key)
    time.sleep(API_CALL_DELAY)

    bep20_transfers = []
    classification = {"type": "Other", "main_token_symbol": None, "main_token_quantity": 0.0, "main_token_address": None}
    estimated_value = {"amount": None, "currency": None, "basis": "N/A"}

    if not receipt_data or "logs" not in receipt_data:
        # print(f"      Backend: No receipt/logs for {tx_hash}")
        return bep20_transfers, classification, estimated_value

    wallet_address_lower = wallet_address_main.lower()
    sent_by_wallet = []
    received_by_wallet = []

    for log_entry in receipt_data.get("logs", []):
        log_topics = log_entry.get("topics", [])
        if log_topics and len(log_topics) == 3 and log_topics[0].lower() == BEP20_TRANSFER_EVENT_SIGNATURE:
            token_addr = log_entry.get("address", "").lower()
            from_addr = decode_address_from_topic(log_topics[1])
            to_addr = decode_address_from_topic(log_topics[2])
            raw_amount_hex = log_entry.get("data")

            if not all([token_addr, from_addr, to_addr, raw_amount_hex is not None]): continue
            
            from_addr = from_addr.lower()
            to_addr = to_addr.lower()

            token_info = get_token_info_server(token_addr, current_bsc_api_key) # Pass API key if needed by underlying
            raw_amount_int = hex_to_int(raw_amount_hex)
            human_amount = 0.0
            human_amount_str = "Error"
            if raw_amount_int is not None and token_info.get("decimals") is not None:
                try:
                    human_amount = raw_amount_int / (10**token_info["decimals"])
                    human_amount_str = f"{human_amount:.8f}".rstrip('0').rstrip('.') # Clean trailing zeros
                except: human_amount_str = f"{raw_amount_int} (raw)"
            
            transfer = {
                "token_address": token_addr, "token_name": token_info["name"],
                "token_symbol": token_info["symbol"], "from": from_addr, "to": to_addr,
                "raw_amount": str(raw_amount_int) if raw_amount_int is not None else "N/A",
                "human_readable_amount": human_amount_str, "decimals": token_info.get("decimals"),
                "numeric_amount": human_amount # For calculations
            }
            bep20_transfers.append(transfer)

            if from_addr == wallet_address_lower: sent_by_wallet.append(transfer)
            if to_addr == wallet_address_lower: received_by_wallet.append(transfer)
    
    # --- Transaction Classification & Value Estimation Logic (Simplified from previous version) ---
    primary_sent_quote_token = next((t for t in sent_by_wallet if t['token_address'] in QUOTE_TOKEN_ADDRESSES), None)
    primary_received_main_token = next((t for t in received_by_wallet if t['token_address'] not in QUOTE_TOKEN_ADDRESSES), None)
    primary_sent_main_token = next((t for t in sent_by_wallet if t['token_address'] not in QUOTE_TOKEN_ADDRESSES), None)
    primary_received_quote_token = next((t for t in received_by_wallet if t['token_address'] in QUOTE_TOKEN_ADDRESSES), None)

    if primary_sent_quote_token and primary_received_main_token:
        classification["type"] = f"Buy" # Simplified type for frontend
        classification["main_token_symbol"] = primary_received_main_token['token_symbol']
        classification["main_token_quantity"] = primary_received_main_token['numeric_amount']
        classification["main_token_address"] = primary_received_main_token['token_address']
        
        quote_val = primary_sent_quote_token['numeric_amount']
        basis_str = f"Sent {quote_val:.4f} {primary_sent_quote_token['token_symbol']}"
        if primary_sent_quote_token['token_address'] == USDT_ADDRESS:
            estimated_value = {"amount": str(quote_val), "currency": "USDT", "basis": basis_str}
        elif primary_sent_quote_token['token_address'] == BUSD_ADDRESS:
            estimated_value = {"amount": str(quote_val), "currency": "BUSD", "basis": basis_str}
        elif primary_sent_quote_token['token_address'] == WBNB_ADDRESS:
            bnb_price = get_historical_bnb_price_server(tx_date_for_price)
            if bnb_price:
                estimated_value = {"amount": str(quote_val * bnb_price), "currency": "USDT (from WBNB)", "basis": f"{basis_str} @ ${bnb_price:.2f}"}
            else: estimated_value["basis"] = f"{basis_str}, BNB price N/A"

    elif primary_sent_main_token and primary_received_quote_token:
        classification["type"] = f"Sell" # Simplified type
        classification["main_token_symbol"] = primary_sent_main_token['token_symbol']
        classification["main_token_quantity"] = primary_sent_main_token['numeric_amount']
        classification["main_token_address"] = primary_sent_main_token['token_address']

        quote_val = primary_received_quote_token['numeric_amount']
        basis_str = f"Received {quote_val:.4f} {primary_received_quote_token['token_symbol']}"
        if primary_received_quote_token['token_address'] == USDT_ADDRESS:
            estimated_value = {"amount": str(quote_val), "currency": "USDT", "basis": basis_str}
        elif primary_received_quote_token['token_address'] == BUSD_ADDRESS:
            estimated_value = {"amount": str(quote_val), "currency": "BUSD", "basis": basis_str}
        elif primary_received_quote_token['token_address'] == WBNB_ADDRESS:
            bnb_price = get_historical_bnb_price_server(tx_date_for_price)
            if bnb_price:
                estimated_value = {"amount": str(quote_val * bnb_price), "currency": "USDT (from WBNB)", "basis": f"{basis_str} @ ${bnb_price:.2f}"}
            else: estimated_value["basis"] = f"{basis_str}, BNB price N/A"
    
    elif sent_by_wallet and not received_by_wallet:
        classification["type"] = f"Send"
    elif not sent_by_wallet and received_by_wallet:
        classification["type"] = f"Receive"
    elif not bep20_transfers:
        classification["type"] = "Interaction / Native Tx"
        
    # print(f"      Backend: Tx {tx_hash[:10]} Classified: {classification['type']}. Val: {estimated_value.get('amount')}")
    return bep20_transfers, classification, estimated_value


def process_wallet_data(target_wallet_address, bsc_api_key):
    # Clear caches for each new request if desired, or manage them for longer periods
    global token_info_cache, bnb_price_cache
    token_info_cache = {}
    bnb_price_cache = {}

# 定义北京时区 (UTC+8)
    beijing_tz = dt_timezone(BEIJING_TIMEZONE_OFFSET)
    
    # 获取当前时间（带UTC时区）
    now_utc = datetime.now(dt_timezone.utc)
    
    # 转换为北京时间
    now_beijing = now_utc.astimezone(beijing_tz)
    today_beijing = now_beijing.date()
    
    # 构造开始时间（北京时间今天8:00）
    start_datetime_beijing = datetime(
        today_beijing.year, today_beijing.month, today_beijing.day, 
        8, 0, 0, tzinfo=beijing_tz
    )
    
    # 如果当前北京时间早于8:00，则使用昨天8:00作为开始
    if now_beijing < start_datetime_beijing:
        start_datetime_beijing -= timedelta(days=1)
    
    # 结束时间是开始时间+24小时
    end_datetime_beijing = start_datetime_beijing + timedelta(days=1)
    
    # 转换为UTC
    start_datetime_utc = start_datetime_beijing.astimezone(dt_timezone.utc)
    end_datetime_utc = end_datetime_beijing.astimezone(dt_timezone.utc)
    
    # 如果结束时间超过当前时间，则使用当前时间作为结束
    if end_datetime_utc > now_utc:
        end_datetime_utc = now_utc
    
    start_timestamp_unix_utc = int(start_datetime_utc.timestamp())
    end_timestamp_unix_utc = int(end_datetime_utc.timestamp())

    start_block = get_block_number_by_timestamp_bsc_server(start_timestamp_unix_utc, 'after', bsc_api_key)
    end_block = get_block_number_by_timestamp_bsc_server(end_timestamp_unix_utc, 'before', bsc_api_key)

    all_transactions_details = []
    asset_holdings_fifo = defaultdict(deque)
    realized_trades_log = []
    all_txs_in_block_range_count = 0

    if start_block is None or end_block is None or start_block > end_block:
        raise Exception("Could not determine valid block range for the given time period.")

    all_txs_in_block_range = fetch_wallet_transactions_by_blockrange_server(target_wallet_address, start_block, end_block, bsc_api_key)
    all_txs_in_block_range_count = len(all_txs_in_block_range)
    
    filtered_txs_in_time_window = [
        tx for tx in all_txs_in_block_range
        if tx.get("timeStamp") and start_timestamp_unix_utc <= int(tx["timeStamp"]) < end_timestamp_unix_utc
    ]

    if not filtered_txs_in_time_window:
        # Return empty but valid structure if no transactions
        pass # Processing loop won't run

    for tx_summary in filtered_txs_in_time_window:
        tx_hash = tx_summary.get("hash")
        if not tx_hash: continue

        tx_main_from_address = tx_summary.get("from", "").lower()
        tx_timestamp_unix = int(tx_summary.get("timeStamp", 0))
        tx_datetime_utc = datetime.fromtimestamp(tx_timestamp_unix, dt_timezone.utc) if tx_timestamp_unix else None
        tx_timestamp_utc_str = tx_datetime_utc.strftime('%Y-%m-%d %H:%M:%S UTC') if tx_datetime_utc else "N/A"
        tx_date_for_price = tx_datetime_utc.strftime('%d-%m-%Y') if tx_datetime_utc else None

        bep20_list, classification_details, estimated_val_details = \
            get_bep20_transfers_and_classify_server(tx_hash, target_wallet_address, tx_date_for_price, tx_timestamp_unix, bsc_api_key)
        
        tx_pnl_current_tx = 0.0
        current_tx_usdt_value_float = 0.0
        
        if estimated_val_details.get("amount"):
            try:
                temp_val = float(estimated_val_details["amount"])
                if estimated_val_details.get("currency") == "BUSD" or "USDT" in estimated_val_details.get("currency", ""):
                    current_tx_usdt_value_float = temp_val
            except: pass # Ignore parsing error for this specific calculation

        if classification_details["type"] == "Buy" and classification_details["main_token_symbol"] and current_tx_usdt_value_float > 0:
            token_sym = classification_details["main_token_symbol"]
            qty_bought = classification_details["main_token_quantity"]
            cost_total_usdt = current_tx_usdt_value_float
            if qty_bought > 0:
                cost_pu_usdt = cost_total_usdt / qty_bought
                asset_holdings_fifo[token_sym].append({
                    "qty": qty_bought, "cost_pu_usdt": cost_pu_usdt, 
                    "tx_hash_buy": tx_hash, "timestamp_buy": tx_timestamp_unix
                })

        elif classification_details["type"] == "Sell" and classification_details["main_token_symbol"] and current_tx_usdt_value_float > 0:
            token_sym = classification_details["main_token_symbol"]
            qty_sold = classification_details["main_token_quantity"]
            proceeds_total_usdt = current_tx_usdt_value_float
            
            if qty_sold > 0 and token_sym in asset_holdings_fifo and asset_holdings_fifo[token_sym]:
                proceeds_pu_usdt = proceeds_total_usdt / qty_sold
                qty_remaining_to_sell = qty_sold
                
                while qty_remaining_to_sell > 0 and asset_holdings_fifo[token_sym]:
                    buy_lot = asset_holdings_fifo[token_sym][0]
                    qty_from_lot = min(qty_remaining_to_sell, buy_lot["qty"])
                    cost_basis_for_lot_portion = qty_from_lot * buy_lot["cost_pu_usdt"]
                    pnl_for_lot_portion = (qty_from_lot * proceeds_pu_usdt) - cost_basis_for_lot_portion
                    tx_pnl_current_tx += pnl_for_lot_portion

                    realized_trades_log.append({
                        "token_symbol": token_sym, "buy_tx_hash": buy_lot["tx_hash_buy"], "sell_tx_hash": tx_hash,
                        "buy_timestamp": buy_lot["timestamp_buy"], "sell_timestamp": tx_timestamp_unix,
                        "quantity_matched": round(qty_from_lot, 8),
                        "buy_cost_per_unit_usdt": round(buy_lot["cost_pu_usdt"], 4),
                        "sell_proceeds_per_unit_usdt": round(proceeds_pu_usdt, 4),
                        "pnl": round(pnl_for_lot_portion, 2)
                    })
                    buy_lot["qty"] -= qty_from_lot
                    if buy_lot["qty"] < 1e-9: asset_holdings_fifo[token_sym].popleft()
                    qty_remaining_to_sell -= qty_from_lot

        if estimated_val_details.get("amount") is None and tx_summary.get("value","0").isdigit() and int(tx_summary.get("value",0)) > 0:
            native_bnb_amount = int(tx_summary.get("value")) / (10**18)
            bnb_price = get_historical_bnb_price_server(tx_date_for_price)
            if bnb_price:
                estimated_val_details = {
                    "amount": str(native_bnb_amount * bnb_price),
                    "currency": "USDT (from native BNB)",
                    "basis": f"{native_bnb_amount:.6f} native BNB @ ${bnb_price:.2f}"
                }
        
        all_transactions_details.append({
            "hash": tx_hash, "block_number": tx_summary.get("blockNumber"),
            "timestamp_unix": tx_timestamp_unix, "timestamp_utc": tx_timestamp_utc_str,
            "tx_from_address": tx_main_from_address, "tx_to_address": tx_summary.get("to", "").lower(),
            "value_bnb_native": str(int(tx_summary.get("value",0))/(10**18)) if tx_summary.get("value","0").isdigit() else "0",
            "gas_used": tx_summary.get("gasUsed"), "is_error": tx_summary.get("isError", "0") == "1",
            "classification_details": classification_details,
            "estimated_transaction_value_usdt_equivalent": estimated_val_details,
            "realized_pnl_for_this_sell_tx_usdt": f"{tx_pnl_current_tx:.2f}" if classification_details["type"] == "Sell" else None,
            "bep20_token_transfers": bep20_list,
        })

    total_realized_pnl_all_trades = sum(trade['pnl'] for trade in realized_trades_log)
    total_loss_value_from_trades = sum(trade['pnl'] for trade in realized_trades_log if trade['pnl'] < 0)
    buy_transaction_count = 0
    sell_transaction_count = 0
    total_usdt_volume_buys = 0.0
    total_usdt_volume_all_txs = 0.0

    for tx_detail in all_transactions_details:
        classification_type = tx_detail.get("classification_details",{}).get("type","Other")
        if classification_type == "Buy": buy_transaction_count += 1 # Use exact match from classification
        elif classification_type == "Sell": sell_transaction_count += 1

        est_val = tx_detail.get("estimated_transaction_value_usdt_equivalent", {})
        val_amount_str = est_val.get("amount")
        if val_amount_str:
            try:
                val_float = float(val_amount_str)
                if "USDT" in est_val.get("currency","") or est_val.get("currency") == "BUSD":
                    total_usdt_volume_all_txs += val_float
                    if classification_type == "Buy": total_usdt_volume_buys += val_float
            except: pass

    return {
        "summary": {
            "wallet_address": target_wallet_address,
            "time_window_beijing": f"{start_datetime_beijing.strftime('%Y-%m-%d %H:%M:%S')} to {end_datetime_beijing.strftime('%Y-%m-%d %H:%M:%S')} CST",
            "time_window_utc": f"{start_datetime_utc.strftime('%Y-%m-%d %H:%M:%S')} to {end_datetime_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "block_range_queried": f"{start_block} - {end_block}" if start_block and end_block else "N/A",
            "transactions_in_block_range_initially_fetched": all_txs_in_block_range_count,
            "transactions_in_precise_time_window_processed": len(all_transactions_details),
            "buy_transaction_count": buy_transaction_count,
            "sell_transaction_count": sell_transaction_count,
            "total_estimated_usdt_volume_all_txs_in_window": f"{total_usdt_volume_all_txs:.2f} USDT",
            "total_estimated_usdt_volume_buys_in_window": f"{total_usdt_volume_buys:.2f} USDT",
            "total_realized_pnl_from_trades_usdt (差值总和)": f"{total_realized_pnl_all_trades:.2f} USDT",
            "total_realized_loss_value_usdt (损耗值)": f"{abs(total_loss_value_from_trades):.2f} USDT",
            "data_generation_date_utc": datetime.now(dt_timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        },
        "realized_trades_log_fifo": realized_trades_log, # Renamed for clarity
        "transactions_in_time_window": all_transactions_details,
        "outstanding_holdings_fifo": {token: list(lots) for token, lots in asset_holdings_fifo.items()}
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_transactions', methods=['POST'])
def get_transactions_route():
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address')
        bsc_api_key = data.get('bsc_api_key')

        if not wallet_address or not wallet_address.startswith('0x'):
            return jsonify({"error": "Invalid or missing wallet address."}), 400
        if not bsc_api_key: # Basic check, could be more robust
            return jsonify({"error": "Missing BscScan API Key."}), 400

        # Call the main processing function from your script
        processed_data = process_wallet_data(wallet_address, bsc_api_key)
        return jsonify(processed_data)

    except Exception as e:
        app.logger.error(f"Error processing request: {e}", exc_info=True) # Log full traceback
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) # debug=True is for development only