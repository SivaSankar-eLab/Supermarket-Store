/**
 * Supermarket Operations Dashboard Client Logic
 * Real-time Chart.js dashboards, catalog CRUD, customer credit ledger, and AI vision scanner
 */

let currentPeriod = 'week';
let chartInstances = {};

// Format currency
const formatINR = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val || 0);

// Toast helper
function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  document.getElementById('toastMsg').innerText = msg;
  t.style.display = 'inline-flex';
  setTimeout(() => { t.style.display = 'none'; }, 3200);
  if (window.feather) feather.replace();
}

// Real-time clock
function updateLiveClock() {
  const clockEl = document.getElementById('liveClock');
  if (!clockEl) return;
  const now = new Date();
  clockEl.innerText = now.toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateLiveClock, 1000);
updateLiveClock();

// Tab switching
function switchTab(tabId, el) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  const target = document.getElementById('tab-' + tabId);
  if (target) target.classList.add('active');

  if (tabId === 'inventory') loadInventory();
  if (tabId === 'invoices') loadBills();
  if (tabId === 'credit' || tabId === 'khata') loadCredit();
  if (window.feather) feather.replace();
}

// Period switching
function setPeriod(p, el) {
  currentPeriod = p;
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');
  const badge = document.getElementById('trendPeriodBadge');
  if (badge) badge.innerText = 'THIS ' + p.toUpperCase();
  const dlBtn = document.getElementById('downloadPptxBtn');
  if (dlBtn) dlBtn.href = '/api/dashboard/export-deck?period=' + p;
  const ctaBtn = document.getElementById('ctaExportBtn');
  if (ctaBtn) ctaBtn.href = '/api/dashboard/export-deck?period=' + p;
  refreshDashboard();
}

// Main fetch
async function refreshDashboard() {
  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) refreshBtn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;"></div> Syncing...';

  try {
    const res = await fetch('/api/dashboard/stats?period=' + currentPeriod);
    const data = await res.json();
    if (!data.ok) throw new Error('API Error');

    // Update Shop Info
    if (data.shop) {
      const nameEl = document.getElementById('shopName');
      if (nameEl) nameEl.innerText = data.shop.name;
      const aiEl = document.getElementById('aiBadge');
      if (aiEl) aiEl.innerText = 'AI: ' + (data.shop.ai_provider || 'GEMINI').toUpperCase();
    }

    // Update KPIs
    if (data.sales) {
      document.getElementById('kpiRevenue').innerText = formatINR(data.sales.revenue);
      document.getElementById('kpiAvgDaily').innerText = 'Daily avg: ' + formatINR(data.sales.avg_daily_revenue);
      document.getElementById('kpiBills').innerText = data.sales.bills + ' Bills';
      document.getElementById('kpiAvgBill').innerText = 'Avg ticket: ' + formatINR(data.sales.avg_bill_value);
      document.getElementById('kpiGst').innerText = formatINR(data.sales.gst_collected);
    }
    const cData = data.credit || data.khata;
    if (cData) {
      const kpiCred = document.getElementById('kpiCredit') || document.getElementById('kpiKhata');
      if (kpiCred) kpiCred.innerText = formatINR(cData.total_dues || 0);
      const kpiCount = document.getElementById('kpiCreditCount') || document.getElementById('kpiKhataCount');
      if (kpiCount) kpiCount.innerText = (cData.count || 0) + ' accounts with dues';
    }
    if (data.stock_health) {
      document.getElementById('kpiSkus').innerText = data.stock_health.total_skus + ' SKUs';
      document.getElementById('kpiStockAlerts').innerText = data.stock_health.low_stock_count + ' low stock alerts';
    }

    // Render Charts
    renderTrendChart(data.daily_breakdown);
    renderPaymentChart(data.payment_breakdown);
    renderTopProductsChart(data.top_products);
    if (data.gst) renderGstSlabChart(data.gst.slabs);

  } catch (err) {
    console.error('Failed to load stats:', err);
  } finally {
    if (refreshBtn) refreshBtn.innerHTML = '<i data-feather="refresh-cw"></i> Refresh';
    if (window.feather) feather.replace();
  }
}

// Chart: Daily Trend
function renderTrendChart(dailyData) {
  const canvas = document.getElementById('trendChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (chartInstances.trend) chartInstances.trend.destroy();

  const labels = (dailyData || []).map(d => d.date.slice(5));
  const revenues = (dailyData || []).map(d => d.revenue);

  chartInstances.trend = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.length ? labels : ['No Data'],
      datasets: [{
        label: 'Sales (₹)',
        data: revenues.length ? revenues : [0],
        backgroundColor: '#FB923C',
        borderColor: '#FDBA74',
        borderRadius: 6,
        borderWidth: 1,
        maxBarThickness: 45,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ' Revenue: ' + formatINR(ctx.raw)
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94A3B8', font: { family: 'Plus Jakarta Sans' } }
        },
        y: {
          grid: { color: '#243048' },
          ticks: {
            color: '#94A3B8',
            font: { family: 'Plus Jakarta Sans' },
            callback: (val) => '₹' + val.toLocaleString('en-IN')
          }
        }
      }
    }
  });
}

// Chart: Payment Mix
function renderPaymentChart(paymentData) {
  const canvas = document.getElementById('paymentChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (chartInstances.payment) chartInstances.payment.destroy();

  const labels = (paymentData || []).map(p => p.mode);
  const totals = (paymentData || []).map(p => p.total);
  const colors = ['#38BDF8', '#818CF8', '#FB923C', '#10B981'];

  chartInstances.payment = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.length ? labels : ['No Sales'],
      datasets: [{
        data: totals.length ? totals : [1],
        backgroundColor: colors.slice(0, Math.max(labels.length, 1)),
        borderColor: '#131B2E',
        borderWidth: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94A3B8', boxWidth: 12, font: { family: 'Plus Jakarta Sans', size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ' ' + ctx.label + ': ' + formatINR(ctx.raw)
          }
        }
      }
    }
  });
}

// Chart: Top Products
function renderTopProductsChart(topItems) {
  const canvas = document.getElementById('topProductsChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (chartInstances.topProducts) chartInstances.topProducts.destroy();

  const labels = (topItems || []).map(p => p.name.length > 16 ? p.name.slice(0, 16) + '…' : p.name);
  const values = (topItems || []).map(p => p.revenue);

  chartInstances.topProducts = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.length ? labels : ['No Items'],
      datasets: [{
        axis: 'y',
        label: 'Revenue (₹)',
        data: values.length ? values : [0],
        backgroundColor: '#10B981',
        borderRadius: 6,
        maxBarThickness: 28,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ' ' + formatINR(ctx.raw)
          }
        }
      },
      scales: {
        x: {
          grid: { color: '#243048' },
          ticks: {
            color: '#94A3B8',
            callback: (v) => '₹' + v.toLocaleString('en-IN')
          }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#F8FAFC', font: { family: 'Plus Jakarta Sans', size: 11 } }
        }
      }
    }
  });
}

// Chart: GST Slabs
function renderGstSlabChart(slabs) {
  const canvas = document.getElementById('gstSlabChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (chartInstances.gst) chartInstances.gst.destroy();

  const labels = (slabs || []).map(s => s.slab + '% GST');
  const values = (slabs || []).map(s => s.total_gst);
  const colors = ['#10B981', '#FBBF24', '#FB923C', '#818CF8', '#EC4899'];

  chartInstances.gst = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels.length ? labels : ['0% GST'],
      datasets: [{
        data: values.length ? values : [1],
        backgroundColor: colors.slice(0, Math.max(labels.length, 1)),
        borderColor: '#131B2E',
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94A3B8', boxWidth: 12, font: { family: 'Plus Jakarta Sans', size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ' ' + ctx.label + ': ' + formatINR(ctx.raw)
          }
        }
      }
    }
  });
}

// Load Inventory Table
let debounceTimer;
function debounceInventory() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadInventory, 300);
}

async function loadInventory() {
  const search = document.getElementById('inventorySearch')?.value || '';
  const lowOnly = document.getElementById('lowStockOnlyCheck')?.checked || false;
  const slab = document.getElementById('slabFilter')?.value || '';
  const tbody = document.getElementById('inventoryTableBody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/dashboard/inventory?search=' + encodeURIComponent(search) + '&low_stock_only=' + lowOnly + '&slab=' + slab);
    const data = await res.json();
    if (!data.ok || !data.products.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:2rem;">No products found matching criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = data.products.map(p => {
      let tagClass = 'stock-healthy';
      let statusText = 'In Stock';
      if (p.is_out_of_stock) {
        tagClass = 'stock-out'; statusText = 'Out of Stock';
      } else if (p.is_low_stock) {
        tagClass = 'stock-low'; statusText = 'Low Stock';
      }

      return `<tr>
        <td style="font-weight:600;">${p.name}</td>
        <td style="color:var(--text-muted);">${p.brand || '—'}</td>
        <td><span class="badge" style="background:var(--surface);">${p.unit}</span></td>
        <td style="font-weight:700;color:var(--accent-coral);">${formatINR(p.sell_price)}</td>
        <td style="color:var(--text-muted);">${formatINR(p.cost_price)}</td>
        <td style="font-weight:700;">${p.qty_on_hand} ${p.unit}</td>
        <td style="color:var(--text-muted);">${p.reorder_level} ${p.unit}</td>
        <td>${p.gst_slab}%</td>
        <td><span class="stock-badge ${tagClass}">${statusText}</span></td>
      </tr>`;
    }).join('');

  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--accent-coral);padding:2rem;">Failed to load inventory.</td></tr>';
  }
}

// Load Bills Table
async function loadBills() {
  const tbody = document.getElementById('billsTableBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/dashboard/bills?limit=40');
    const data = await res.json();
    if (!data.ok || !data.bills.length) {
      tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted);padding:2rem;">No finalized bills found.</td></tr>';
      return;
    }

    tbody.innerHTML = data.bills.map(b => {
      let payTag = 'stock-healthy';
      if (b.payment_mode === 'UPI') payTag = 'stock-low';
      if (b.payment_mode === 'KHATA') payTag = 'stock-out';

      return `<tr>
        <td><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--accent-blue);">#${b.short_id}</span></td>
        <td style="color:var(--text-muted);">${b.finalized_at}</td>
        <td style="font-weight:600;">${b.customer_name}</td>
        <td><span class="stock-badge ${payTag}">${b.payment_mode}</span></td>
        <td>${b.items_count} items</td>
        <td>${formatINR(b.subtotal)}</td>
        <td style="color:var(--accent-saffron);">${formatINR(b.total_gst)}</td>
        <td style="font-weight:800;color:var(--accent-teal);">${formatINR(b.grand_total)}</td>
        <td>
          <a href="/api/dashboard/download-invoice/${b.id}" class="btn btn-secondary" style="padding:0.3rem 0.65rem;font-size:0.75rem;" target="_blank">
            <i data-feather="file" style="width:12px;height:12px;"></i> PDF
          </a>
        </td>
      </tr>`;
    }).join('');
    if (window.feather) feather.replace();

  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--accent-coral);padding:2rem;">Failed to load bills.</td></tr>';
  }
}

// Load Credit Ledger Table
async function loadCredit() {
  const tbody = document.getElementById('creditTableBody') || document.getElementById('khataTableBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/dashboard/stats?period=week');
    const data = await res.json();
    const credit = data.credit || data.khata || { total_dues: 0, customers: [] };

    const headerTotalEl = document.getElementById('creditHeaderTotal') || document.getElementById('khataHeaderTotal');
    if (headerTotalEl) headerTotalEl.innerText = 'Total Outstanding: ' + formatINR(credit.total_dues);

    if (!credit.customers || !credit.customers.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--accent-teal);padding:2rem;">🎉 No outstanding customer dues! All accounts settled.</td></tr>';
      return;
    }

    tbody.innerHTML = credit.customers.map((c, i) => `<tr>
      <td style="color:var(--text-muted);">${i + 1}</td>
      <td style="font-weight:700;">${c.name}</td>
      <td style="color:var(--text-muted);font-family:'JetBrains Mono',monospace;">${c.phone || '—'}</td>
      <td style="font-weight:800;color:var(--accent-coral);font-size:0.95rem;">${formatINR(c.balance)}</td>
      <td>
        <div style="display:flex;gap:0.5rem;">
          <button class="btn btn-secondary" onclick="viewCustomerStatement('${c.id}', '${c.name}')" style="padding:0.3rem 0.65rem;font-size:0.75rem;">
            <i data-feather="list" style="width:12px;height:12px;"></i> Statement
          </button>
          <button class="btn btn-secondary" onclick="copyWhatsAppReminder('${c.name}', '${c.phone || ''}', ${c.balance})" style="padding:0.3rem 0.65rem;font-size:0.75rem;background:rgba(16,185,129,0.1);color:#34D399;border-color:rgba(16,185,129,0.3);">
            <i data-feather="message-circle" style="width:12px;height:12px;"></i> Copy Reminder
          </button>
        </div>
      </td>
    </tr>`).join('');
    if (window.feather) feather.replace();

  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--accent-coral);padding:2rem;">Failed to load customer credit ledger.</td></tr>';
  }
}
const loadKhata = loadCredit;

// Customer Statement Modal
async function viewCustomerStatement(customerId, customerName) {
  document.getElementById('modalCustomerName').innerText = customerName + ' — Ledger Statement';
  document.getElementById('statementModal').classList.add('open');
  const body = document.getElementById('modalStatementBody');
  body.innerHTML = '<div style="text-align:center;padding:2rem;"><div class="spinner"></div> Loading transactions...</div>';

  try {
    const res = await fetch('/api/dashboard/credit/statement/' + customerId);
    const data = await res.json();
    if (!data.ok || !data.transactions.length) {
      body.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:2rem;">No transaction entries found for this customer.</div>';
      return;
    }

    let rowsHtml = data.transactions.map(t => {
      const isCredit = t.type === 'CREDIT';
      return `<tr>
        <td style="color:var(--text-muted);">${t.created_at}</td>
        <td><span class="stock-badge ${isCredit ? 'stock-out' : 'stock-healthy'}">${t.type}</span></td>
        <td style="font-weight:700;color:${isCredit ? '#F87171' : '#34D399'}">${isCredit ? '+' : '-'}${formatINR(t.amount)}</td>
        <td style="color:var(--text-muted);">${t.mode || '—'}</td>
        <td style="color:var(--text-muted);font-size:0.8rem;">${t.note || (t.ref_bill_id ? 'Bill #' + t.ref_bill_id : '—')}</td>
      </tr>`;
    }).join('');

    body.innerHTML = `
      <div style="background:var(--surface);padding:0.85rem 1.25rem;border-radius:10px;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div style="font-size:0.75rem;color:var(--text-muted);">CURRENT OUTSTANDING</div>
          <div style="font-size:1.4rem;font-weight:800;color:var(--accent-coral);">${formatINR(data.customer.current_balance)}</div>
        </div>
        <div style="font-size:0.85rem;color:var(--text-muted);">📱 ${data.customer.phone || 'No Phone'}</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Date & Time</th>
              <th>Type</th>
              <th>Amount</th>
              <th>Mode</th>
              <th>Reference / Note</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    `;

  } catch (e) {
    body.innerHTML = '<div style="text-align:center;color:var(--accent-coral);padding:2rem;">Failed to fetch customer statement.</div>';
  }
}

function closeStatementModal() {
  document.getElementById('statementModal').classList.remove('open');
}

function copyWhatsAppReminder(name, phone, balance) {
  const shop = document.getElementById('shopName')?.innerText || 'Our Store';
  const text = `Hello ${name}, this is a polite reminder from ${shop} regarding your outstanding account balance of ₹${balance.toFixed(2)}. Kindly clear at your earliest convenience. Thank you!`;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied WhatsApp reminder message to clipboard!');
  }).catch(() => {
    alert(text);
  });
}

// Add Product Modal
function openAddProductModal() {
  document.getElementById('addProductModal').classList.add('open');
}
function closeAddProductModal() {
  document.getElementById('addProductModal').classList.remove('open');
}

async function submitModalAddProduct() {
  const name = document.getElementById('modalAddName').value.trim();
  const sell = parseFloat(document.getElementById('modalAddSell').value);
  if (!name || isNaN(sell) || sell <= 0) {
    alert('Please enter a valid product name and selling price.');
    return;
  }

  const btn = document.getElementById('modalAddSubmitBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:6px;"></div> Saving...';

  const payload = {
    name: name,
    brand: document.getElementById('modalAddBrand').value.trim(),
    unit: document.getElementById('modalAddUnit').value.trim() || 'kg',
    gst_slab: parseFloat(document.getElementById('modalAddGst').value),
    sell_price: sell,
    cost_price: parseFloat(document.getElementById('modalAddCost').value) || Math.round(sell * 0.82),
    initial_qty: parseFloat(document.getElementById('modalAddQty').value) || 0,
    reorder_level: parseFloat(document.getElementById('modalAddReorder').value) || 0,
  };

  try {
    const res = await fetch('/api/dashboard/add-product', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      showToast('Product registered in catalog successfully!');
      closeAddProductModal();
      loadInventory();
      refreshDashboard();
    } else {
      alert('Failed: ' + (data.error?.message || 'Validation error'));
    }
  } catch (e) {
    alert('Network error adding product.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Save to Inventory';
  }
}

// ── Vision & Barcode Scanning Logic ────────────────────────────────────
let selectedVisionFile = null;

function handleImageSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  selectedVisionFile = file;

  const reader = new FileReader();
  reader.onload = (event) => {
    document.getElementById('imagePreview').src = event.target.result;
    document.getElementById('previewContainer').style.display = 'block';
    document.getElementById('dropZone').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

function clearImagePreview() {
  selectedVisionFile = null;
  document.getElementById('visionFileInput').value = '';
  document.getElementById('imagePreview').src = '';
  document.getElementById('previewContainer').style.display = 'none';
  document.getElementById('dropZone').style.display = 'block';
}

async function runScan() {
  const barcodeVal = document.getElementById('barcodeInput').value.trim();
  if (!selectedVisionFile && !barcodeVal) {
    alert('Please select an image to scan or enter a barcode number.');
    return;
  }

  const scanBtn = document.getElementById('scanSubmitBtn');
  const placeholder = document.getElementById('scanPlaceholder');
  const loading = document.getElementById('scanLoading');
  const content = document.getElementById('scanContent');
  const statusBadge = document.getElementById('scanStatusBadge');

  scanBtn.disabled = true;
  scanBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;margin-right:6px;"></div> Analyzing Image...';
  placeholder.style.display = 'none';
  content.style.display = 'none';
  loading.style.display = 'block';

  try {
    const formData = new FormData();
    if (selectedVisionFile) formData.append('file', selectedVisionFile);
    if (barcodeVal) formData.append('barcode', barcodeVal);

    const res = await fetch('/api/dashboard/scan-product', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    loading.style.display = 'none';
    content.style.display = 'flex';
    statusBadge.style.display = 'inline-flex';

    if (!data.ok) {
      statusBadge.className = 'badge stock-out';
      statusBadge.innerText = 'NOT RECOGNIZED';
      content.innerHTML = `
        <div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:12px;padding:1.5rem;text-align:center;">
          <div style="font-size:2rem;margin-bottom:0.5rem;">⚠️</div>
          <div style="font-weight:700;color:#F87171;font-size:1.05rem;">Unrecognized Item</div>
          <div style="font-size:0.85rem;color:var(--text-muted);margin-top:0.35rem;">${data.error?.message || 'Could not identify a clear grocery packaging label or barcode. Try uploading a clearer photo.'}</div>
        </div>`;
      return;
    }

    const isMatched = data.data.status === 'MATCHED_IN_CATALOG';
    const detected = data.data.detected || {};

    if (isMatched) {
      const p = data.data.product;
      statusBadge.className = 'badge badge-live';
      statusBadge.innerText = '🎯 MATCHED IN CATALOG';

      content.innerHTML = `
        <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);border-radius:14px;padding:1.25rem;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;">
            <div>
              <div style="font-size:0.75rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:0.05em;">Catalog Item Found</div>
              <div style="font-size:1.35rem;font-weight:800;color:#FFFFFF;margin-top:0.2rem;">${p.display_name}</div>
              <div style="font-size:0.85rem;color:var(--text-muted);">${p.brand || 'No Brand'} • Unit: <span class="badge" style="background:var(--surface);">${p.unit}</span></div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:0.75rem;color:var(--text-muted);">Selling Price</div>
              <div style="font-size:1.5rem;font-weight:800;color:var(--accent-coral);">${formatINR(p.sell_price)}</div>
              ${p.mrp ? `<div style="font-size:0.75rem;color:var(--text-muted);text-decoration:line-through;">MRP ${formatINR(p.mrp)}</div>` : ''}
            </div>
          </div>

          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.75rem;margin-top:1rem;background:var(--surface);border-radius:10px;padding:0.85rem;">
            <div>
              <div style="font-size:0.72rem;color:var(--text-muted);font-weight:600;">STOCK ON HAND</div>
              <div style="font-size:1.15rem;font-weight:800;color:${p.is_out_of_stock ? '#F87171' : (p.is_low_stock ? '#FBBF24' : '#34D399')}">${p.qty_on_hand} ${p.unit}</div>
            </div>
            <div>
              <div style="font-size:0.72rem;color:var(--text-muted);font-weight:600;">GST SLAB</div>
              <div style="font-size:1.15rem;font-weight:800;color:var(--text-main);">${p.gst_slab}%</div>
            </div>
            <div>
              <div style="font-size:0.72rem;color:var(--text-muted);font-weight:600;">BARCODE</div>
              <div style="font-size:0.85rem;font-weight:700;color:var(--accent-blue);font-family:'JetBrains Mono',monospace;margin-top:0.2rem;">${p.barcode || detected.barcode || '—'}</div>
            </div>
          </div>

          <div style="margin-top:1rem;display:flex;gap:0.75rem;">
            <button class="btn btn-secondary" onclick="switchTab('inventory', document.querySelector('.tab-btn:nth-child(3)'))" style="flex:1;justify-content:center;">
              <i data-feather="box"></i> View in Inventory
            </button>
          </div>
        </div>`;
    } else {
      const sug = data.data.suggested_product || {};
      statusBadge.className = 'badge badge-ai';
      statusBadge.innerText = '✨ NEW PRODUCT SUGGESTION';

      content.innerHTML = `
        <div style="background:rgba(129,140,248,0.1);border:1px solid rgba(129,140,248,0.25);border-radius:14px;padding:1.25rem;">
          <div style="font-size:0.75rem;font-weight:700;color:#A5B4FC;text-transform:uppercase;letter-spacing:0.05em;">AI Detected New SKU</div>
          <div style="font-size:1.25rem;font-weight:800;color:#FFFFFF;margin-top:0.2rem;">${sug.brand ? sug.brand + ' ' : ''}${sug.name}</div>
          <div style="font-size:0.82rem;color:var(--text-muted);margin-top:0.25rem;">This item is not in your catalog yet. Review details below and click Add to Catalog.</div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-top:1rem;">
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Product Name</label>
              <input id="newProdName" type="text" value="${sug.name || ''}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Brand</label>
              <input id="newProdBrand" type="text" value="${sug.brand || ''}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Unit</label>
              <input id="newProdUnit" type="text" value="${sug.unit || 'pkt'}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">GST Slab (%)</label>
              <select id="newProdGst" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;">
                <option value="0" ${sug.gst_slab === 0 ? 'selected' : ''}>0% (Nil / Essential)</option>
                <option value="5" ${sug.gst_slab === 5 ? 'selected' : ''}>5% (Groceries & Essentials)</option>
                <option value="12" ${sug.gst_slab === 12 ? 'selected' : ''}>12% (Standard)</option>
                <option value="18" ${sug.gst_slab === 18 ? 'selected' : ''}>18% (Packaged/Personal)</option>
                <option value="28" ${sug.gst_slab === 28 ? 'selected' : ''}>28% (Luxury)</option>
              </select>
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">MRP (₹)</label>
              <input id="newProdMrp" type="number" step="0.5" value="${sug.mrp || 0}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" oninput="document.getElementById('newProdSell').value = this.value" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Selling Price (₹)</label>
              <input id="newProdSell" type="number" step="0.5" value="${sug.sell_price || sug.mrp || 0}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Cost Price (₹)</label>
              <input id="newProdCost" type="number" step="0.5" value="${sug.cost_price || Math.round((sug.sell_price || 10) * 0.82)}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Barcode Number</label>
              <input id="newProdBarcode" type="text" value="${sug.barcode || ''}" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Opening Stock Qty</label>
              <input id="newProdQty" type="number" value="10" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
            <div>
              <label style="font-size:0.72rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;">Reorder Alert Level</label>
              <input id="newProdReorder" type="number" value="3" style="width:100%;background:var(--surface);border:1px solid var(--border);color:#fff;padding:0.45rem 0.65rem;border-radius:8px;margin-top:0.2rem;font-family:inherit;font-size:0.85rem;" />
            </div>
          </div>

          <button id="addCatalogBtn" class="btn btn-primary" onclick="submitAddNewProduct()" style="width:100%;justify-content:center;margin-top:1.25rem;padding:0.65rem;background:linear-gradient(135deg,#10B981,#059669);border:none;">
            <i data-feather="plus-circle"></i> Add to Store Catalog
          </button>
        </div>`;
    }

    if (window.feather) feather.replace();

  } catch (err) {
    console.error('Scan failed:', err);
    loading.style.display = 'none';
    content.style.display = 'flex';
    content.innerHTML = `<div style="color:var(--accent-coral);text-align:center;padding:2rem;">Network or server error analyzing image.</div>`;
  } finally {
    scanBtn.disabled = false;
    scanBtn.innerHTML = '<i data-feather="zap"></i> Identify Product & Match Catalog';
    if (window.feather) feather.replace();
  }
}

async function submitAddNewProduct() {
  const btn = document.getElementById('addCatalogBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:6px;"></div> Adding...';

  const payload = {
    name: document.getElementById('newProdName').value,
    brand: document.getElementById('newProdBrand').value,
    unit: document.getElementById('newProdUnit').value,
    gst_slab: parseFloat(document.getElementById('newProdGst').value),
    mrp: parseFloat(document.getElementById('newProdMrp').value) || null,
    sell_price: parseFloat(document.getElementById('newProdSell').value),
    cost_price: parseFloat(document.getElementById('newProdCost').value),
    barcode: document.getElementById('newProdBarcode').value,
    initial_qty: parseFloat(document.getElementById('newProdQty').value) || 0,
    reorder_level: parseFloat(document.getElementById('newProdReorder').value) || 0,
  };

  try {
    const res = await fetch('/api/dashboard/add-product', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      showToast('Product successfully added to catalog!');
      refreshDashboard();
      runScan(); // re-verify scan as matched
    } else {
      alert('❌ Failed to add product: ' + (data.error?.message || 'Validation error'));
    }
  } catch (e) {
    alert('Network error adding product.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-feather="plus-circle"></i> Add to Store Catalog';
    if (window.feather) feather.replace();
  }
}

// Init on load
document.addEventListener('DOMContentLoaded', () => {
  if (window.feather) feather.replace();
  refreshDashboard();
});
