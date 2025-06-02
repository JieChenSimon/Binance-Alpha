document.getElementById('submitBtn').addEventListener('click', async function() {
    const walletAddress = document.getElementById('walletAddress').value.trim();
    const apiKey = document.getElementById('apiKey').value.trim();
    const resultsArea = document.getElementById('resultsArea');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorDisplay = document.getElementById('errorDisplay');

    resultsArea.style.display = 'none';
    errorDisplay.style.display = 'none';
    errorDisplay.textContent = '';

    if (!walletAddress || !walletAddress.startsWith('0x')) {
        errorDisplay.textContent = 'Please enter a valid Wallet Address starting with 0x.';
        errorDisplay.style.display = 'block';
        return;
    }
    if (!apiKey) {
        errorDisplay.textContent = 'Please enter your BscScan API Key.';
        errorDisplay.style.display = 'block';
        return;
    }

    loadingIndicator.style.display = 'block';

    try {
        const response = await fetch('/get_transactions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ wallet_address: walletAddress, bsc_api_key: apiKey }),
        });

        loadingIndicator.style.display = 'none';

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: `HTTP error! Status: ${response.status}` }));
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
             throw new Error(data.error);
        }

        displaySummary(data.summary);
        displayTransactionsTable(data.transactions_in_time_window);
        displayRealizedTradesTable(data.realized_trades_log_fifo);
        displayOutstandingHoldings(data.outstanding_holdings_fifo);
        resultsArea.style.display = 'block';

    } catch (error) {
        loadingIndicator.style.display = 'none';
        console.error('Error fetching or processing data:', error);
        errorDisplay.textContent = `An error occurred: ${error.message}`;
        errorDisplay.style.display = 'block';
    }
});

function displaySummary(summary) {
    const summaryDiv = document.getElementById('summaryDetails');
    summaryDiv.innerHTML = ''; // Clear previous
    if (!summary) return;

    const ul = document.createElement('ul');
    for (const key in summary) {
        const li = document.createElement('li');
        const readableKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()); // Make key readable
        li.innerHTML = `<strong>${readableKey}:</strong> ${summary[key]}`;
        ul.appendChild(li);
    }
    summaryDiv.appendChild(ul);
}

function displayTransactionsTable(transactions) {
    const table = document.getElementById('transactionsTable');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    thead.innerHTML = '';
    tbody.innerHTML = '';

    if (!transactions || transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10">No transactions found in the specified time window.</td></tr>';
        return;
    }

    // Define desired headers and the corresponding data keys
    // Adjusted to match the Python output structure more closely
    const headers = [
        { key: "hash", display: "Hash" },
        { key: "timestamp_utc", display: "Timestamp (UTC)" },
        { key: "classification_details.type", display: "Type (Wallet)" },
        { key: "classification_details.main_token_symbol", display: "Main Token" },
        { key: "classification_details.main_token_quantity", display: "Main Token Qty" },
        { key: "estimated_transaction_value_usdt_equivalent.amount", display: "Est. Value" },
        { key: "estimated_transaction_value_usdt_equivalent.currency", display: "Value Currency" },
        { key: "realized_pnl_for_this_sell_tx_usdt", display: "Realized P/L (This Tx)" },
        { key: "tx_from_address", display: "From" },
        { key: "tx_to_address", display: "To" },
        // { key: "bep20_token_transfers", display: "BEP20 Transfers (Details)"} // Might be too complex for simple cell
    ];

    const trHead = document.createElement('tr');
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header.display;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    transactions.forEach(tx => {
        const tr = document.createElement('tr');
        headers.forEach(header => {
            const td = document.createElement('td');
            let value = getNestedValue(tx, header.key);
            if (value === null || value === undefined) value = 'N/A';
            
            if (header.key === "hash" || header.key === "tx_from_address" || header.key === "tx_to_address") {
                const shortVal = value.length > 12 ? `${value.substring(0, 6)}...${value.substring(value.length - 4)}` : value;
                const link = document.createElement('a');
                link.href = `https://bscscan.com/tx/${tx.hash}`; // Link for hash, adjust for addresses
                if(header.key !== "hash") link.href = `https://bscscan.com/address/${value}`;
                link.textContent = shortVal;
                link.target = "_blank";
                td.appendChild(link);
            } else if (typeof value === 'object') {
                td.textContent = JSON.stringify(value, null, 2).substring(0, 100) + "..."; // Simple display for objects
            } else {
                td.textContent = value;
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function displayRealizedTradesTable(trades) {
    const table = document.getElementById('realizedTradesTable');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    thead.innerHTML = '';
    tbody.innerHTML = '';

    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8">No realized trades (FIFO) logged for this period.</td></tr>';
        return;
    }
    const headers = [
        { key: "token_symbol", display: "Token" },
        { key: "quantity_matched", display: "Qty Matched" },
        { key: "buy_cost_per_unit_usdt", display: "Buy Cost/Unit (USDT)" },
        { key: "sell_proceeds_per_unit_usdt", display: "Sell Price/Unit (USDT)" },
        { key: "pnl", display: "P/L (USDT)" },
        { key: "buy_tx_hash", display: "Buy Tx" },
        { key: "sell_tx_hash", display: "Sell Tx" },
        { key: "sell_timestamp", display: "Sell Timestamp" }
    ];
    const trHead = document.createElement('tr');
    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header.display;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    trades.forEach(trade => {
        const tr = document.createElement('tr');
        headers.forEach(header => {
            const td = document.createElement('td');
            let value = getNestedValue(trade, header.key);
            if (value === null || value === undefined) value = 'N/A';
            
            if (header.key === "sell_timestamp" || header.key === "buy_timestamp") {
                 value = new Date(value * 1000).toLocaleString();
            } else if (typeof value === 'number' && (header.key.includes('pnl') || header.key.includes('cost') || header.key.includes('proceeds'))){
                 value = value.toFixed(2);
            } else if (typeof value === 'number' && header.key.includes('quantity')){
                 value = value.toFixed(6);
            }


            if (header.key === "buy_tx_hash" || header.key === "sell_tx_hash") {
                const shortVal = value.length > 12 ? `${value.substring(0, 6)}...${value.substring(value.length - 4)}` : value;
                const link = document.createElement('a');
                link.href = `https://bscscan.com/tx/${value}`;
                link.textContent = shortVal;
                link.target = "_blank";
                td.appendChild(link);
            } else {
                td.textContent = value;
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}


function displayOutstandingHoldings(holdings) {
    const div = document.getElementById('outstandingHoldings');
    div.innerHTML = '';
    if (!holdings || Object.keys(holdings).length === 0) {
        div.textContent = 'No outstanding holdings (FIFO) at the end of the period based on fetched transactions.';
        return;
    }

    for (const tokenSymbol in holdings) {
        const tokenLots = holdings[tokenSymbol];
        if (tokenLots.length > 0) {
            const tokenHeader = document.createElement('h4');
            tokenHeader.textContent = `Token: ${tokenSymbol}`;
            div.appendChild(tokenHeader);

            const ul = document.createElement('ul');
            tokenLots.forEach(lot => {
                const li = document.createElement('li');
                const buyDate = new Date(lot.timestamp_buy * 1000).toLocaleDateString();
                li.textContent = `Qty: ${lot.qty.toFixed(6)}, Cost/Unit: $${lot.cost_pu_usdt.toFixed(4)} (Bought on ${buyDate}, Tx: ${lot.tx_hash_buy.substring(0,10)}...)`;
                ul.appendChild(li);
            });
            div.appendChild(ul);
        }
    }
}


function getNestedValue(obj, path) {
    if (!path) return obj;
    const parts = path.split('.');
    let current = obj;
    for (let i = 0; i < parts.length; i++) {
        if (current && typeof current === 'object' && parts[i] in current) {
            current = current[parts[i]];
        } else {
            return undefined; // Path does not exist
        }
    }
    return current;
}