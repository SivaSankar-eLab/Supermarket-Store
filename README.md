<div align="center">

# 🏪 SupermarketBot
### AI-Powered Supermarket & Retail Store Operations Agent

<img src="supermarket_agent_architecture.png" alt="SupermarketBot Architecture" width="850"/>

> A production-grade **Telegram chatbot + Web Dashboard** for supermarket and retail store management —  
> built with a custom **Multi-Provider Agent Harness**, **PostgreSQL 16** event-sourced ledgers,  
> and mathematically guaranteed **GST compliance**.

[![Telegram Bot](https://img.shields.io/badge/Telegram-@mykiranastore__bot-26A5E4?logo=telegram&logoColor=white&style=for-the-badge)](https://t.me/mykiranastore_bot)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white&style=for-the-badge)](https://python.org)
[![Claude SDK](https://img.shields.io/badge/Claude-Agent_SDK-D97757?logo=anthropic&logoColor=white&style=for-the-badge)](https://anthropic.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google&logoColor=white&style=for-the-badge)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white&style=for-the-badge)](https://postgresql.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-009688?logo=fastapi&logoColor=white&style=for-the-badge)](https://fastapi.tiangolo.com)

**🤖 Live Bot:** [`@mykiranastore_bot`](https://t.me/mykiranastore_bot) — *Active & Ready to Message*

</div>

---

## 📋 Table of Contents

1. [Overview](#-1-overview)
2. [Screenshots & Demo](#-2-screenshots--demo)
3. [Tech Stack](#-3-tech-stack)
4. [Architecture & Agent Harness](#-4-architecture--agent-harness)
5. [Control Loop](#-5-control-loop)
6. [Skills & Tools (31 Tools)](#-6-skills--tools-31-tools)
7. [Hard Problems & Solutions](#-7-hard-problems--solutions)
8. [Stretch Capabilities](#-8-stretch-capabilities)
9. [Project Structure](#-9-project-structure)
10. [Quick Start](#-10-quick-start)
11. [Environment Variables](#-11-environment-variables)
12. [Testing](#-12-testing)
13. [Demo Walkthrough](#-13-demo-walkthrough)
14. [Collaborators](#-14-collaborators)

---

## 🌟 1. Overview

**SupermarketBot** is an autonomous AI agent designed for supermarket and grocery retail managers. It transforms everyday Telegram messages — plain English, product photos, and barcodes — into accurate accounting, inventory, and billing operations.

### ✨ Key Capabilities

| Feature | Description |
|:---|:---|
| 📦 **Inventory Management** | Loose and packaged SKUs, stock ledger, low-stock alerts, barcode & product image recognition |
| 🧾 **Draft & Final Billing** | Multi-turn draft bills with live edits, atomic checkout, and oversell protection |
| 💳 **Customer Credit Ledger** | Digital khata for customer credit, UPI/cash settlements, outstanding balances |
| 📄 **Automated Documents** | Instant GST-compliant PDF invoices with HSN codes + PowerPoint analytics decks with real charts |
| 🧠 **Durable Memory** | Standing store preferences that persist across session resets (`/new`) |
| 🎙️ **Voice Orders** | Telegram voice note → draft bill transcription |
| 🌐 **Multi-Language** | English, Hindi, Tamil, and Hinglish |
| 📷 **Vision AI** | Real-time product identification from product photos and barcodes |

---

## 📸 2. Screenshots & Demo

> 📁 All screenshots, documents, and the demo video are in [`screenshort_video and document/`](./screenshort_video%20and%20document/)

### Dashboard & Bot in Action

<table>
  <tr>
    <td align="center"><img src="screenshort_video and document/1.png" width="360"/><br/><sub>📊 Web Dashboard — Live Overview</sub></td>
    <td align="center"><img src="screenshort_video and document/2.png" width="360"/><br/><sub>🤖 Telegram Bot — Inventory Query</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/3.png" width="360"/><br/><sub>🧾 Draft Bill — Multi-turn Edit</sub></td>
    <td align="center"><img src="screenshort_video and document/4.png" width="360"/><br/><sub>✅ Bill Finalized — GST Applied</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/5.png" width="360"/><br/><sub>📄 PDF Invoice — GST Compliant</sub></td>
    <td align="center"><img src="screenshort_video and document/6.png" width="360"/><br/><sub>💳 Customer Credit Ledger</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/7.png" width="360"/><br/><sub>📈 Analytics — Sales Summary</sub></td>
    <td align="center"><img src="screenshort_video and document/8.png" width="360"/><br/><sub>📊 PowerPoint Analytics Deck</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/9.png" width="360"/><br/><sub>🔔 Low Stock Alert</sub></td>
    <td align="center"><img src="screenshort_video and document/10.png" width="360"/><br/><sub>📦 Stock Receive — Batch Tracking</sub></td>
  </tr>
  <tr>
    <td align="center" colspan="2"><img src="screenshort_video and document/11.png" width="740"/><br/><sub>🏗️ Full Architecture Diagram</sub></td>
  </tr>
</table>

### 📁 Documents & Media

| File | Description |
|:---|:---|
| [`invoice_707AF91A.pdf`](./screenshort_video%20and%20document/invoice_707AF91A.pdf) | Sample GST-compliant invoice (WeasyPrint rendered) |
| [`invoice_CDB2640F.pdf`](./screenshort_video%20and%20document/invoice_CDB2640F.pdf) | Sample GST-compliant invoice with CGST+SGST breakdown |
| [`analysis_today_2026-09-08.pptx`](./screenshort_video%20and%20document/analysis_today_2026-09-08.pptx) | Auto-generated PowerPoint analytics deck with real charts |
| `video.mp4` | Full demo video — *hosted externally (197 MB — exceeds GitHub limit)* |

---

## 🛠️ 3. Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **AI / LLM** | Claude 3.5 Sonnet (Anthropic) | Primary reasoning & tool-calling agent |
| **AI / LLM** | Gemini 2.5 Flash / Flash Lite | Vision tasks & fallback provider |
| **Backend** | FastAPI + Uvicorn | Async REST API & Telegram webhook server |
| **Database** | PostgreSQL 16 + asyncpg | ACID-compliant, row-locked ledger store |
| **Migrations** | Alembic | Schema versioning & migration management |
| **Messaging** | Telegram Bot API | Primary owner interface |
| **Dashboard** | FastAPI HTML + Jinja2 | Real-time web operations dashboard |
| **Documents** | WeasyPrint + python-pptx | PDF invoice & PowerPoint analytics generation |
| **Charts** | Matplotlib | Embedded charts in PPTX analytics decks |
| **FTS / Search** | PostgreSQL `pg_trgm` | Fuzzy product name matching |
| **Precision Math** | Python `Decimal` | GST/paise-accurate financial calculations |
| **Testing** | pytest + pytest-asyncio | 49-test suite with concurrency stress tests |
| **Containerization** | Docker + docker-compose | One-command deployment |

---

## 🏗️ 4. Architecture & Agent Harness

### Framework: Custom Multi-Provider Agent Harness

Built on the **Claude Agent SDK pattern** with native support for:
- **Claude 3.5 Sonnet** (primary reasoning & financial operations)
- **Google Gemini 2.5 Flash / Flash Lite** (vision tasks & secondary provider)

### Why This Harness?

| Design Decision | Rationale |
|:---|:---|
| **Deterministic Tool Schemas** | Strict JSON schema definitions prevent tool hallucination; enforce exact typing for financial parameters |
| **Defense-in-Depth Guard Hooks** | `PreToolUse` & `PostToolUse` hooks execute independent DB checks before mutating operations |
| **Stateful Context + Stateless Isolation** | Conversational context across multi-turn edits; all ledger state delegated to PostgreSQL transactions |
| **Sub-Second Latency** | High execution speed for conversational responsiveness with multimodal (vision) support |

---

## 🔄 5. Control Loop

The agent operates on an **Observe → Reason → Guard → Execute → Verify → Respond** loop:

```
[Owner Input: Text / Photo / Barcode / Voice Transcript]
                          │
                          ▼
             [Load Context & Preferences]
  (Fetches store defaults from PostgreSQL by shop_id; survives /new)
                          │
                          ▼
            [LLM Reasoning & Tool Selection]
    (Claude / Gemini maps intent to 31 registered tool schemas)
                          │
                          ▼
            [PreToolUse Guardrail Hook]
   (Independent DB query checks stock, cost floor & customer validity)
                          │
                          ▼
            [Tool Execution & DB Transaction]
 (PostgreSQL 16: SELECT FOR UPDATE row locks + Event-Sourced Ledgers)
                          │
                          ▼
            [Artifact Generation / Result Eval]
  (Renders WeasyPrint PDF invoice or python-pptx presentation deck)
                          │
                          ▼
             [Telegram Response Delivery]
   (Sends structured message, PDF, or PPTX directly to the owner)
```

### Step-by-Step

1. **Receive & Deduplicate** — Telegram bridge receives updates; `update_id` uniqueness verified to eliminate network retries
2. **Inject Durable Memory** — Store preferences loaded from PostgreSQL and injected into prompt context
3. **Plan & Call Tools** — LLM determines appropriate tools (e.g., `pg_trgm` fuzzy search or draft bill creation)
4. **PreToolUse Guardrails** — Independent code hooks re-verify constraints before dangerous actions
5. **Atomic Commit** — Changes committed in PostgreSQL using row locks; zero overselling guaranteed
6. **Generate Output** — PDF invoice or PPTX analytics deck rendered and dispatched to Telegram

---

## 🧰 6. Skills & Tools (31 Tools)

KiranaBot exposes **31 tools across 7 skill domains**:

### 📦 Inventory (10 tools)
| Tool | Purpose |
|:---|:---|
| `find_product` | Search products using `pg_trgm` fuzzy text matching |
| `get_stock` | Check live stock-on-hand for any SKU |
| `list_low_stock` | List items at or below reorder threshold |
| `add_product` | Create new SKU with unit, HSN code, and GST slab |
| `receive_stock` | Record wholesale inventory delivery with cost/selling prices |
| `adjust_stock` | Adjust inventory for wastage, spoilage, or damage |
| `list_products` | List all active store inventory |
| `update_product_price` | Update selling price or MRP of a product |
| `lookup_by_barcode` | Query item by standard barcode number (EAN-13/UPC) |
| `list_batches_fefo` | Prioritize batches by Expiry Date (First-Expired, First-Out) |

### 🧾 Billing (8 tools)
| Tool | Purpose |
|:---|:---|
| `start_bill` | Create a new multi-turn draft bill |
| `add_bill_item` | Add item and quantity to active draft bill |
| `update_bill_item` | Modify item quantity or unit price in draft bill |
| `remove_bill_item` | Remove line item from active draft |
| `get_draft_bill` | View active draft bill with line totals and GST preview |
| `finalize_bill` | Atomic checkout: validates stock, locks rows, logs sale, applies GST |
| `void_bill` | Cancel finalized bill and reverse stock movements |
| `list_bills` | View recent bills and payment histories |

### 💳 Customer Credit & Accounts (6 tools)
| Tool | Purpose |
|:---|:---|
| `add_customer` | Create new customer account with phone number |
| `find_customer` | Look up customer record by name or phone |
| `get_customer_balance` | Compute ledger balance (`SUM(CREDIT) - SUM(PAYMENT)`) |
| `add_credit` | Record goods given on credit |
| `record_payment` | Record debt settlement via Cash or UPI |
| `list_customers_with_dues` | List all customers with outstanding balances |
| `get_customer_statement` | Retrieve chronological statement of credit & payments |
| `create_payment_reminder` | Generate multilingual payment reminder message with UPI link |

### 📈 Analytics (4 tools)
| Tool | Purpose |
|:---|:---|
| `daily_close` | End-of-day register closing report (Cash, UPI, Credit totals) |
| `sales_summary` | Revenue breakdown and top-selling SKUs over time |
| `gst_collected` | Tax report categorized by GST slabs (0%, 5%, 12%, 18%, 28%) |
| `reorder_suggestions` | Compute sales velocity (units/day) & suggest reorder quantities |

### 📄 Documents (2 tools)
| Tool | Purpose |
|:---|:---|
| `generate_invoice_pdf` | Render clean, GST-compliant WeasyPrint PDF invoice |
| `generate_analysis_deck` | Generate PowerPoint (PPTX) analytics presentation with real charts |

### ⚙️ Preferences (3 tools)
| Tool | Purpose |
|:---|:---|
| `set_preference` | Store persistent configuration key-value in PostgreSQL |
| `get_preference` | Retrieve store preference value |
| `list_preferences` | View all active store preferences |

### 👁️ Vision (1 tool)
| Tool | Purpose |
|:---|:---|
| `identify_product_from_image` | Detect product brand, name, size & barcode from photos |

---

## 🔥 7. Hard Problems & Solutions

### Problem 1: Overselling Under High Concurrency
> **Issue**: Concurrent checkout requests for the same stock can cause negative inventory.

**Solution**: Implemented `SELECT ... FOR UPDATE` row-level locks on product records ordered deterministically by `product_id` (preventing deadlocks). Verified via automated concurrency stress test — **50 concurrent requests competing for 20 units → exactly 20 succeed, 30 rejected cleanly**.

---

### Problem 2: GST Calculation Errors & Floating-Point Drift
> **Issue**: Standard IEEE-754 floating-point arithmetic causes rounding discrepancies on tax slabs and paise calculations.

**Solution**: Dedicated GST calculation engine using Python's `Decimal` module with explicit `ROUND_HALF_UP` rounding. Correctly handles 50/50 intra-state CGST + SGST splits, HSN lookup, and invoice round-off adjustments.

---

### Problem 3: Multi-Turn Draft Billing with Incremental Corrections
> **Issue**: Store owners make real-time changes during a sale ("add 2kg sugar... actually make it 3kg") before finalizing payment.

**Solution**: Stateful draft bill sessions in PostgreSQL. Items can be added, updated, or removed across conversational turns. Stock is only locked and deducted upon explicit `finalize_bill`.

---

### Problem 4: Idempotency & Accidental Duplicate Operations
> **Issue**: Network timeouts and Telegram webhook retries can cause duplicate bill finalizations or double-payments.

**Solution**: Unique `idempotency_key` constraint on bills + `processed_telegram_updates` ledger that rejects duplicate update IDs at the bridge level.

---

### Problem 5: Memory Loss Across `/new` Sessions
> **Issue**: Standard chat LLM memory wipes store configuration when a session is cleared.

**Solution**: Decoupled conversation history from store configuration. Standing preferences stored in PostgreSQL keyed by `shop_id` and dynamically loaded into system context on every new session.

---

### Problem 6: Selling Below Cost & Invalid Customer Credit Entries
> **Issue**: Risk of accidental deep discounting below wholesale cost or extending credit to nonexistent customers.

**Solution**: Enforced validation in `finalize_bill` (rejecting transactions where total revenue < total cost) and customer foreign key constraints in credit ledger transactions.

---

## 🚀 8. Stretch Capabilities

All **8 stretch capabilities** are fully implemented and production-ready:

| # | Feature | Details |
|:---|:---|:---|
| 🎨 | **Branded PDF Invoices** | Professional Jinja2 + WeasyPrint template with store branding, GSTIN, HSN codes, 50/50 CGST+SGST |
| 📅 | **Scheduled Weekly Deck** | Automated Monday morning scheduler generating executive PPTX with real Matplotlib charts |
| 📈 | **Sales Velocity Reorder** | Historical sales velocity (units/day), days of remaining inventory, exact reorder quantities |
| ⏳ | **Expiry / Batch FEFO Tracking** | Inventory batch tracking prioritized by First-Expired, First-Out — eliminates grocery waste |
| 🎙️ | **Voice-Note Orders** | Telegram voice note (.oga/.ogg/.mp3) download + multimodal transcription into draft bills |
| 🌐 | **Multi-Language Support** | Native understanding in English, Hindi, Tamil, and Hinglish |
| 📷 | **Barcode / Product Photo AI** | Real-time product identification from photos and packaging via Gemini Vision |
| 🔔 | **Credit Payment Reminders** | Auto-generates polite localized payment reminders with direct UPI pay links |

---

## 📁 9. Project Structure

```
supermarket/
├── app/                          # Core application
│   ├── agent.py                  # Multi-provider agent harness (Claude + Gemini)
│   ├── config.py                 # Environment config & settings
│   ├── database.py               # Async PostgreSQL connection pool
│   ├── dashboard.py              # FastAPI web dashboard routes
│   ├── hooks.py                  # PreToolUse & PostToolUse guardrail hooks
│   ├── main.py                   # FastAPI app entry point & Telegram webhook
│   ├── models.py                 # SQLAlchemy ORM models (products, bills, ledgers)
│   ├── telegram_bridge.py        # Telegram message handler & update deduplicator
│   ├── providers/                # LLM provider abstraction layer
│   └── tools/                    # 31 tool implementations
│       ├── analytics.py          # daily_close, sales_summary, gst_collected, reorder
│       ├── billing.py            # start_bill, add_item, finalize_bill, void_bill...
│       ├── credit.py             # add_customer, add_credit, record_payment...
│       ├── documents.py          # generate_invoice_pdf, generate_analysis_deck
│       ├── gst_utils.py          # Decimal-precision GST calculation engine
│       ├── inventory.py          # find_product, add_product, receive_stock...
│       ├── preferences.py        # set_preference, get_preference, list_preferences
│       └── vision.py             # identify_product_from_image
├── alembic/                      # Database migrations
│   └── versions/
│       └── 001_initial_schema.py # Initial schema migration
├── frontend/                     # Web dashboard templates & static assets
│   ├── static/                   # CSS, JS, images
│   └── templates/                # Jinja2 HTML templates (dashboard + invoice)
├── scripts/                      # Utility & verification scripts
│   ├── poll_telegram.py          # Long-polling Telegram updates (dev mode)
│   ├── seed_data.py              # Development data seeder
│   ├── schedule_weekly_deck.py   # Monday morning PPTX scheduler
│   ├── verify_capabilities.py    # 11-capability verification suite
│   ├── verify_hard_parts.py      # 9-hard-problem verification suite
│   └── verify_stretch_goals.py   # 8-stretch-goal verification suite
├── tests/                        # pytest test suite (49 tests)
├── skills/                       # Agent skill documentation
├── screenshort_video and document/ # Screenshots, invoices, PPTX, demo video
├── docs_output/                  # Runtime-generated invoices & documents
├── .env.example                  # Environment variable template (copy → .env)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image definition
├── docker-compose.yml            # Multi-service container stack
├── run.bat                       # 1-click Windows launcher
├── stop.bat                      # Clean shutdown script
└── alembic.ini                   # Alembic migration configuration
```

---

## ⚡ 10. Quick Start

### Option A: 1-Click Windows Launcher (Recommended)

```bat
:: Start PostgreSQL, run migrations, launch Dashboard + Bot, open browser
run.bat

:: Stop all services cleanly
stop.bat
```

### Option B: Docker Compose

```bash
# Copy environment template
cp .env.example .env
# Fill in your API keys in .env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec app alembic upgrade head
```

### Option C: Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/SivaSankar-eLab/Supermarket-Store.git
cd Supermarket-Store

# 2. Create Python virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your API keys and database URL

# 5. Start PostgreSQL and run migrations
alembic upgrade head

# 6. Launch the application
python run_all.py

# Or start services individually:
python -m uvicorn app.main:app --port 8000 --reload
python -m scripts.poll_telegram
```

---

## 🔧 11. Environment Variables

Copy `.env.example` → `.env` and fill in your values:

| Variable | Description | Required |
|:---|:---|:---:|
| `ANTHROPIC_API_KEY` | Claude API key from [console.anthropic.com](https://console.anthropic.com) | ✅ |
| `GEMINI_API_KEY` | Google AI Studio key from [aistudio.google.com](https://aistudio.google.com) | ✅ |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) | ✅ |
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://...`) | ✅ |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL (`postgresql://...`) | ✅ |
| `SHOP_ID` | UUID for your store (any UUID v4) | ✅ |
| `SHOP_NAME` | Your store's display name | ✅ |
| `SHOP_OWNER_NAME` | Store owner's name | ✅ |
| `SHOP_GSTIN` | GST Identification Number | ✅ |
| `SHOP_ADDRESS` | Store address (appears on invoices) | ✅ |
| `CLAUDE_MODEL` | Claude model ID (default: `claude-3-5-sonnet-20241022`) | ⬜ |
| `GEMINI_MODEL` | Gemini model ID (default: `gemini-flash-lite-latest`) | ⬜ |
| `WEBHOOK_URL` | Public HTTPS URL for Telegram webhook (production) | ⬜ |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook validation secret (production) | ⬜ |
| `APP_HOST` | Server host (default: `0.0.0.0`) | ⬜ |
| `APP_PORT` | Server port (default: `8000`) | ⬜ |
| `DOCS_OUTPUT_DIR` | Directory for generated PDFs/PPTX | ⬜ |

---

## 🧪 12. Testing

```bash
# Run all 49 pytest unit & integration tests
pytest

# Run with verbose output
pytest -v

# Verify all 11 core store capabilities
python scripts/verify_capabilities.py

# Verify all 9 architectural hard parts & safety guards
python scripts/verify_hard_parts.py

# Verify all 8 advanced enterprise stretch goals
python scripts/verify_stretch_goals.py
```

### Test Coverage

| Suite | Tests | Coverage |
|:---|:---:|:---|
| GST Calculation Engine | 12 | Decimal precision, CGST/SGST splits, HSN codes |
| Concurrency / Oversell Guard | 8 | 50-concurrent-request stress test |
| Draft Billing Multi-Turn | 9 | Add/edit/remove/finalize/void |
| Customer Credit Ledger | 7 | Balance computation, payment recording |
| Document Generation | 6 | PDF invoice, PPTX analytics deck |
| Idempotency & Deduplication | 4 | Duplicate update_id rejection |
| Preferences Persistence | 3 | Cross-session memory |
| **Total** | **49** | All passing ✅ |

---

## 🎬 13. Demo Walkthrough

Test the live bot [`@mykiranastore_bot`](https://t.me/mykiranastore_bot) in sequence:

```
1. Receive Stock
   → "Add 50kg Aashirvaad flour, bought at ₹42, selling at ₹50"

2. Multi-Item Bill with Real-Time Edit
   → "Bill for Ravi: 2kg flour, 1L Saffola oil, 500g sugar"
   → "Wait, make it 3kg flour instead"
   → "Finalize via UPI"

3. Oversell Guard (Safety)
   → "Bill 500kg flour for Suresh"
   ← Bot refuses: "Only X kg available"

4. Customer Credit Ledger Cycle
   → "Sunita took goods worth ₹800 on credit"
   → "Sunita paid ₹500 via UPI"

5. GST-Compliant PDF Invoice
   → "Send me the PDF invoice for Ravi's latest bill"

6. Executive Analytics Deck
   → "Generate a PowerPoint analysis deck for this week's store performance"

7. Preferences & Memory Persistence Across /new
   → "Set default payment method to UPI"
   → "/new"
   → "What is my default payment method?" ← "UPI" (remembered!)
```

---

## 👥 14. Collaborators

| GitHub | Role |
|:---|:---|
| [@SivaSankar-eLab](https://github.com/SivaSankar-eLab) | Project Lead & Primary Developer |
| [@Aswath363](https://github.com/Aswath363) | Collaborator |
| [@akshaiP](https://github.com/akshaiP) | Collaborator |
| [@ashwanthnebula](https://github.com/ashwanthnebula) | Collaborator |

---

## 📜 License

This project is private and proprietary. All rights reserved © 2026 SivaSankar-eLab.

---

<div align="center">

Built with ❤️ using **Claude Agent SDK** · **PostgreSQL 16** · **Telegram Bot API** · **FastAPI**

⭐ *If this project helped you, give it a star!* ⭐

</div>
