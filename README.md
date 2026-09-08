<div align="center">

# 🏪 SupermarketBot
### AI-Powered Supermarket & Retail Store Operations Agent

<img src="supermarket_agent_architecture.png" alt="SupermarketBot Architecture Diagram" width="900"/>

> A **production-grade** Telegram chatbot + Web Dashboard for complete supermarket and retail store management —
> built with a custom **Multi-Provider AI Agent Harness** (Claude + Gemini), **PostgreSQL 16** event-sourced ledgers,
> mathematically guaranteed **GST compliance**, and **8 enterprise stretch capabilities**.

[![Telegram Bot](https://img.shields.io/badge/Telegram-@mykiranastore__bot-26A5E4?logo=telegram&logoColor=white&style=for-the-badge)](https://t.me/mykiranastore_bot)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white&style=for-the-badge)](https://python.org)
[![Claude SDK](https://img.shields.io/badge/Claude-3.5_Sonnet-D97757?logo=anthropic&logoColor=white&style=for-the-badge)](https://anthropic.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google&logoColor=white&style=for-the-badge)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white&style=for-the-badge)](https://postgresql.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-009688?logo=fastapi&logoColor=white&style=for-the-badge)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white&style=for-the-badge)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-49_Passing-brightgreen?logo=pytest&logoColor=white&style=for-the-badge)](#-12-testing)

**🤖 Live Bot:** [`@mykiranastore_bot`](https://t.me/mykiranastore_bot) — *Active & Ready to Message*

</div>

---

## 📋 Table of Contents

1. [Overview](#-1-overview)
2. [Screenshots & Demo](#-2-screenshots--demo)
3. [Media & Document Folder](#-3-media--document-folder)
4. [Tech Stack](#-4-tech-stack)
5. [Architecture & Agent Harness](#-5-architecture--agent-harness)
6. [Control Loop](#-6-control-loop)
7. [Skills & Tools (31 Tools)](#-7-skills--tools-31-tools)
8. [Hard Problems & Solutions](#-8-hard-problems--solutions)
9. [Stretch Capabilities](#-9-stretch-capabilities)
10. [Project Structure](#-10-project-structure)
11. [Quick Start](#-11-quick-start)
12. [Environment Variables](#-12-environment-variables)
13. [Testing](#-13-testing)
14. [Demo Walkthrough](#-14-demo-walkthrough)
15. [Commit History & Progression](#-15-commit-history--progression)
16. [FAQ](#-16-faq)
17. [License](#-17-license)

---

## 🌟 1. Overview

**SupermarketBot** is a fully autonomous AI operations agent designed for supermarket and grocery retail store managers. It transforms everyday Telegram messages — plain English text, product photos, barcodes, and voice notes — into accurate real-time accounting, inventory management, and billing operations.

Built as a **production-grade system**, not a demo or prototype, SupermarketBot solves real operational pain points for small-to-medium retail stores with features that rival enterprise POS systems.

### ✨ Key Capabilities at a Glance

| Feature | Description |
|:---|:---|
| 📦 **Inventory Management** | Loose and packaged SKUs, live stock ledger, low-stock alerts, barcode & product image recognition via AI Vision |
| 🧾 **Draft & Final Billing** | Multi-turn conversational draft bills with live edits, atomic checkout, GST application, and oversell protection |
| 💳 **Customer Credit Ledger** | Full digital khata: credit entries, UPI/cash settlements, outstanding balance queries, payment reminders |
| 📄 **Automated Documents** | Instant GST-compliant PDF invoices with HSN codes + auto-generated PowerPoint analytics decks with real Matplotlib charts |
| 🧠 **Durable Memory** | Store preferences persist across session resets (`/new`) — set once, remembered forever |
| 🎙️ **Voice Orders** | Telegram voice note (.oga/.ogg) → transcribed → draft bill in seconds |
| 🌐 **Multi-Language** | Native understanding of English, Hindi, Tamil, and Hinglish |
| 📷 **Vision AI** | Real-time product brand, name, weight, and barcode identification from product photos |
| 🔄 **Idempotency** | Webhook retry deduplication prevents duplicate billing or double payments |
| 📊 **Analytics & Reporting** | Daily close reports, weekly sales summary, GST ledger, sales velocity, reorder suggestions |

---

## 📸 2. Screenshots & Demo

> 📁 All screenshots, demo video and documents are located in [`screenshort_video and document/`](./screenshort_video%20and%20document/)

### Dashboard & Bot in Action

<table>
  <tr>
    <td align="center"><img src="screenshort_video and document/1.png" width="360"/><br/><sub>📊 Web Dashboard — Live Overview</sub></td>
    <td align="center"><img src="screenshort_video and document/2.png" width="360"/><br/><sub>🤖 Telegram Bot — Inventory Query</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/3.png" width="360"/><br/><sub>🧾 Draft Bill — Multi-turn Edit Session</sub></td>
    <td align="center"><img src="screenshort_video and document/4.png" width="360"/><br/><sub>✅ Bill Finalized — GST Auto-Applied</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/5.png" width="360"/><br/><sub>📄 PDF Invoice — GST Compliant Output</sub></td>
    <td align="center"><img src="screenshort_video and document/6.png" width="360"/><br/><sub>💳 Customer Credit Ledger (Khata)</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/7.png" width="360"/><br/><sub>📈 Analytics — Sales Summary Report</sub></td>
    <td align="center"><img src="screenshort_video and document/8.png" width="360"/><br/><sub>📊 PowerPoint Analytics Deck Output</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshort_video and document/9.png" width="360"/><br/><sub>🔔 Low Stock Alert in Telegram</sub></td>
    <td align="center"><img src="screenshort_video and document/10.png" width="360"/><br/><sub>📦 Stock Receive — Batch Tracking</sub></td>
  </tr>
  <tr>
    <td align="center" colspan="2"><img src="screenshort_video and document/11.png" width="740"/><br/><sub>🏗️ Full Agent Architecture Diagram</sub></td>
  </tr>
</table>

---

## 📁 3. Media & Document Folder

All visual documentation, sample outputs, and the demo video are stored in [`screenshort_video and document/`](./screenshort_video%20and%20document/).

### 🖼️ Screenshots Index

| File | What It Shows |
|:---|:---|
| [`1.png`](./screenshort_video%20and%20document/1.png) | Web Dashboard — Real-time live overview with inventory & billing stats |
| [`2.png`](./screenshort_video%20and%20document/2.png) | Telegram Bot — Inventory query via plain English message |
| [`3.png`](./screenshort_video%20and%20document/3.png) | Draft Bill — Multi-turn conversational edit session in Telegram |
| [`4.png`](./screenshort_video%20and%20document/4.png) | Bill Finalized — GST auto-applied with CGST+SGST breakdown |
| [`5.png`](./screenshort_video%20and%20document/5.png) | PDF Invoice — Professional WeasyPrint-rendered GST invoice |
| [`6.png`](./screenshort_video%20and%20document/6.png) | Customer Credit Ledger — Full khata with balance computation |
| [`7.png`](./screenshort_video%20and%20document/7.png) | Analytics Report — Daily and weekly sales summary |
| [`8.png`](./screenshort_video%20and%20document/8.png) | PowerPoint Deck — Auto-generated analytics presentation with charts |
| [`9.png`](./screenshort_video%20and%20document/9.png) | Low Stock Alert — Telegram notification with reorder quantity |
| [`10.png`](./screenshort_video%20and%20document/10.png) | Stock Receive — Batch inventory delivery tracking with cost prices |
| [`11.png`](./screenshort_video%20and%20document/11.png) | Full Architecture Diagram — Complete multi-provider agent flow |

### 📄 Sample Documents

| File | Description |
|:---|:---|
| [`invoice_707AF91A.pdf`](./screenshort_video%20and%20document/invoice_707AF91A.pdf) | Sample GST-compliant PDF invoice (WeasyPrint rendered) with CGST+SGST |
| [`invoice_CDB2640F.pdf`](./screenshort_video%20and%20document/invoice_CDB2640F.pdf) | Sample invoice with CGST + SGST breakdown and HSN codes |
| [`analysis_today_2026-09-08.pptx`](./screenshort_video%20and%20document/analysis_today_2026-09-08.pptx) | Auto-generated PowerPoint analytics deck with real Matplotlib charts |

### 🎬 Demo Video

> **`video.mp4`** — *Full walkthrough demo recording (197 MB)*
>
> ⚠️ This file exceeds GitHub's 100 MB file size limit and is **not stored** in this repository.
>
> **To access the demo video:**
> - Contact the repository owner [@SivaSankar-eLab](https://github.com/SivaSankar-eLab) for an access link
> - Or run the project locally and record your own walkthrough using the [Demo Walkthrough](#-14-demo-walkthrough) guide

---

## 🛠️ 4. Tech Stack

| Layer | Technology | Version | Purpose |
|:---|:---|:---:|:---|
| **AI / LLM (Primary)** | Claude 3.5 Sonnet (Anthropic) | 20241022 | Reasoning, financial tool-calling, multi-turn conversations |
| **AI / LLM (Vision)** | Google Gemini 2.5 Flash | latest | Product identification from photos, multimodal fallback |
| **AI / LLM (Lite)** | Google Gemini Flash Lite | latest | Fast vision tasks, lightweight operations |
| **Backend** | FastAPI + Uvicorn | 0.115+ | Async REST API, Telegram webhook server |
| **Database** | PostgreSQL 16 + asyncpg | 16 | ACID-compliant, row-locked event-sourced ledger |
| **ORM** | SQLAlchemy 2.0 (async) | 2.0.36+ | Async ORM with connection pooling |
| **Migrations** | Alembic | 1.13+ | Schema versioning and automated migration |
| **Messaging** | Telegram Bot API | v7+ | Primary owner interface |
| **Dashboard** | FastAPI + Jinja2 | — | Real-time HTML web operations dashboard |
| **PDF Invoices** | WeasyPrint + Jinja2 | 62.3+ | Professional GST-compliant invoice generation |
| **Analytics Decks** | python-pptx | 1.0.2+ | Auto-generated PowerPoint presentations |
| **Charts** | Matplotlib | 3.9.2+ | Embedded Matplotlib charts in PPTX decks |
| **FTS / Fuzzy Search** | PostgreSQL `pg_trgm` | — | Fuzzy product name matching (typo-tolerant) |
| **Precision Math** | Python `Decimal` | built-in | GST/paise-accurate financial calculations |
| **Container** | Docker + docker-compose | — | One-command full deployment |
| **Testing** | pytest + pytest-asyncio | 8.3.3+ | 49-test suite including concurrency stress tests |

---

## 🏗️ 5. Architecture & Agent Harness

### Custom Multi-Provider Agent Harness

SupermarketBot is built on a **custom agent harness** (not a generic LangChain or off-the-shelf framework) modeled after the Claude Agent SDK pattern, with:

- **Primary**: Claude 3.5 Sonnet — handles all financial tool-calling, multi-turn conversations, and reasoning
- **Secondary**: Google Gemini 2.5 Flash / Flash Lite — handles vision tasks (product photo identification) and serves as a fallback provider
- **Failover**: Automatic provider switching if the primary provider fails or times out

### Why Custom Architecture?

| Design Decision | Rationale |
|:---|:---|
| **Deterministic Tool Schemas** | Strict JSON schema definitions prevent tool hallucination; enforce exact typing for financial parameters (Decimal, UUIDs) |
| **Defense-in-Depth Guard Hooks** | `PreToolUse` & `PostToolUse` hooks run independent DB checks before and after every mutating operation |
| **Stateful Context + Stateless Isolation** | Conversational context maintained across multi-turn edits; all ledger state delegated to PostgreSQL |
| **Event-Sourced Ledgers** | Every financial operation is an immutable event log entry, enabling full audit trail and reversal |
| **Row-Level Locking** | `SELECT ... FOR UPDATE` prevents race conditions in concurrent checkout scenarios |
| **Provider Abstraction** | `app/providers/` layer enables swapping AI providers without changing business logic |

---

## 🔄 6. Control Loop

The agent operates on a strict **Observe → Reason → Guard → Execute → Verify → Respond** loop:

```
[Owner Input: Text / Photo / Barcode / Voice Note]
                         │
                         ▼
         ┌─────────────────────────────────┐
         │     Telegram Bridge Layer       │
         │  • Update deduplication         │
         │  • Media download (photos/audio)│
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │   Load Durable Store Context    │
         │  • Fetch preferences by shop_id │
         │  • Inject into system prompt    │
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │  LLM Reasoning & Tool Selection │
         │  • Claude 3.5 Sonnet (primary)  │
         │  • Gemini Flash (vision/fallback)│
         │  • Maps intent → tool schemas   │
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │     PreToolUse Guard Hook       │
         │  • Validates stock availability │
         │  • Checks cost floor            │
         │  • Verifies customer existence  │
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │  Tool Execution & DB Transaction│
         │  • SELECT FOR UPDATE row locks  │
         │  • Atomic PostgreSQL commits    │
         │  • Event log entry created      │
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │   Artifact Generation / Output  │
         │  • WeasyPrint PDF invoice       │
         │  • python-pptx analytics deck   │
         │  • Structured text response     │
         └───────────────┬─────────────────┘
                         │
                         ▼
         ┌─────────────────────────────────┐
         │    Telegram Response Delivery   │
         │  • Text, PDF, or PPTX to owner  │
         └─────────────────────────────────┘
```

---

## 🧰 7. Skills & Tools (31 Tools)

SupermarketBot exposes **31 tools across 7 skill domains**. Each skill domain is documented in `skills/<domain>/SKILL.md`.

### 📦 Inventory (10 Tools) — `skills/inventory/`

| Tool | Description |
|:---|:---|
| `find_product` | Fuzzy-search products using PostgreSQL `pg_trgm` (typo-tolerant) |
| `get_stock` | Check live stock-on-hand quantity for any SKU |
| `list_low_stock` | List all items at or below their reorder threshold |
| `add_product` | Create new SKU with unit type, HSN code, and GST slab |
| `receive_stock` | Record wholesale inventory delivery with batch tracking and cost/selling prices |
| `adjust_stock` | Adjust inventory for wastage, spoilage, shrinkage, or damage |
| `list_products` | List all active products in the store inventory |
| `update_product_price` | Update the selling price or MRP of an existing product |
| `lookup_by_barcode` | Look up a product by EAN-13/UPC-A barcode |
| `list_batches_fefo` | List batches sorted by First-Expired, First-Out priority |

### 🧾 Billing (8 Tools) — `skills/billing/`

| Tool | Description |
|:---|:---|
| `start_bill` | Create a new stateful draft bill session |
| `add_bill_item` | Add a product and quantity to the active draft bill |
| `update_bill_item` | Modify quantity or unit price for a line item in the draft |
| `remove_bill_item` | Remove a specific line item from the active draft |
| `get_draft_bill` | View the active draft with line totals and GST preview |
| `finalize_bill` | Atomic checkout: validates stock, locks rows, deducts inventory, logs sale, applies GST |
| `void_bill` | Cancel a finalized bill and reverse all stock movements |
| `list_bills` | View recent finalized bills and payment histories |

### 💳 Customer Credit & Accounts (8 Tools) — `skills/khata/`

| Tool | Description |
|:---|:---|
| `add_customer` | Create a new customer account with name and phone |
| `find_customer` | Look up a customer by name or phone number |
| `get_customer_balance` | Compute current outstanding balance (SUM(credit) − SUM(payment)) |
| `add_credit` | Record goods extended to a customer on credit |
| `record_payment` | Record debt settlement via Cash or UPI |
| `list_customers_with_dues` | List all customers with outstanding unpaid balances |
| `get_customer_statement` | Retrieve a chronological statement of all credits and payments |
| `create_payment_reminder` | Generate a multilingual payment reminder with a direct UPI pay link |

### 📈 Analytics (4 Tools) — `skills/analytics/`

| Tool | Description |
|:---|:---|
| `daily_close` | End-of-day register closing report: Cash, UPI, Credit totals |
| `sales_summary` | Revenue breakdown and top-selling SKUs over a time period |
| `gst_collected` | Tax report categorized by GST slabs: 0%, 5%, 12%, 18%, 28% |
| `reorder_suggestions` | Sales velocity (units/day) analysis with exact reorder quantity suggestions |

### 📄 Documents (2 Tools) — `skills/documents/`

| Tool | Description |
|:---|:---|
| `generate_invoice_pdf` | Render a clean, professional GST-compliant PDF invoice via WeasyPrint |
| `generate_analysis_deck` | Generate a PowerPoint (PPTX) analytics presentation with embedded Matplotlib charts |

### ⚙️ Preferences (3 Tools) — `skills/preferences/`

| Tool | Description |
|:---|:---|
| `set_preference` | Store a persistent configuration key-value in PostgreSQL (survives `/new`) |
| `get_preference` | Retrieve a stored preference value by key |
| `list_preferences` | View all active store preferences and their values |

### 👁️ Vision (1 Tool) — `skills/vision/`

| Tool | Description |
|:---|:---|
| `identify_product_from_image` | Detect product brand, name, weight/size, and barcode number from a product photo |

---

## 🔥 8. Hard Problems & Solutions

### ⚡ Problem 1: Overselling Under High Concurrency

> **Issue**: Concurrent checkout requests for the same stock cause negative inventory ("race to zero" problem).

**Solution**: Implemented `SELECT ... FOR UPDATE` row-level locking on product records, ordered deterministically by `product_id` (preventing deadlocks). Verified via automated concurrency stress test:
- **50 concurrent requests competing for 20 units → exactly 20 succeed, 30 rejected cleanly**
- Zero negative stock entries possible

---

### 🔢 Problem 2: GST Calculation Errors & Floating-Point Drift

> **Issue**: Standard IEEE-754 floating-point arithmetic causes rounding discrepancies on tax slabs and paise calculations (e.g., ₹99.99 × 18% ≠ ₹18.00 exactly).

**Solution**: Dedicated GST calculation engine in `app/tools/gst_utils.py` using Python's `Decimal` module with explicit `ROUND_HALF_UP` rounding. Correctly handles:
- 50/50 intra-state CGST + SGST splits
- HSN code lookup for correct slab assignment
- Invoice round-off adjustments to nearest rupee

---

### 📝 Problem 3: Multi-Turn Draft Billing with Incremental Corrections

> **Issue**: Store owners make real-time changes during a sale conversation ("add 2kg sugar... actually make it 3kg... remove the oil") before finalizing.

**Solution**: Stateful draft bill sessions stored in PostgreSQL. Items can be added, updated, or removed across multiple conversational turns. Stock is only locked and deducted upon explicit `finalize_bill` — never during drafting.

---

### 🔁 Problem 4: Idempotency & Duplicate Telegram Operations

> **Issue**: Network timeouts and Telegram webhook retries cause duplicate bill finalizations or double-payments.

**Solution**: Unique `idempotency_key` constraint on bills + `processed_telegram_updates` ledger that rejects duplicate `update_id` values at the bridge level. Every state-mutating operation is safe to retry.

---

### 🧠 Problem 5: Memory Loss Across `/new` Sessions

> **Issue**: Standard chat LLM memory wipes store configuration when a new session is started with `/new`.

**Solution**: Decoupled conversation history from store configuration. Standing preferences stored in PostgreSQL keyed by `shop_id` and dynamically injected into system context on every new session start.

---

### 💰 Problem 6: Selling Below Cost / Invalid Credit Entries

> **Issue**: Risk of accidental deep discounting below wholesale cost, or extending credit to unregistered customers.

**Solution**: `finalize_bill` enforces that total revenue ≥ total cost before committing. Credit entries use database foreign key constraints that reject entries for nonexistent customer IDs.

---

### 🔍 Problem 7: Typo-Tolerant Product Search

> **Issue**: Store owners send "Aashirvad flor" or "asha flour" — exact text matching fails.

**Solution**: PostgreSQL `pg_trgm` trigram similarity index enables fuzzy matching with configurable similarity threshold. Falls back to `rapidfuzz` Python library in test environments without the extension.

---

### 📦 Problem 8: Expiry Date / Batch Tracking

> **Issue**: Grocery items expire and poor batch rotation leads to waste and compliance risk.

**Solution**: Full batch inventory model (`batch_id`, `expiry_date`, `cost_price`) with FEFO (First-Expired, First-Out) prioritization tool. Automatically suggests which batches to sell first.

---

## 🚀 9. Stretch Capabilities

All **8 stretch capabilities** are fully implemented and production-ready:

| # | Feature | Implementation Details |
|:---|:---|:---|
| 🎨 | **Branded PDF Invoices** | Professional Jinja2 + WeasyPrint template with store logo, GSTIN, HSN codes, 50/50 CGST+SGST, auto round-off |
| 📅 | **Scheduled Weekly Deck** | `scripts/schedule_weekly_deck.py` runs Monday morning — auto-generates executive PPTX with real Matplotlib bar/pie charts |
| 📈 | **Sales Velocity Reorder** | Historical velocity (units/day), days-of-inventory remaining, exact reorder quantity by SKU |
| ⏳ | **Expiry / FEFO Batch Tracking** | Full batch model with expiry date — FEFO prioritization eliminates grocery waste |
| 🎙️ | **Voice-Note Orders** | Telegram voice note (.oga/.ogg/.mp3) download + Gemini multimodal transcription → draft bill |
| 🌐 | **Multi-Language Support** | Native understanding of English, Hindi, Tamil, and Hinglish without explicit translation |
| 📷 | **Barcode / Product Photo AI** | Real-time product identification: brand, name, size, barcode from photos via Gemini Vision |
| 🔔 | **Credit Payment Reminders** | Auto-generated multilingual payment reminders with direct UPI deep-link for one-tap payment |

---

## 📁 10. Project Structure

```
supermarket/
├── app/                              # Core application source
│   ├── __init__.py
│   ├── agent.py                      # Multi-provider AI agent harness (Claude + Gemini)
│   ├── config.py                     # Pydantic Settings — environment config & validation
│   ├── database.py                   # Async PostgreSQL connection pool (asyncpg + SQLAlchemy)
│   ├── dashboard.py                  # FastAPI web dashboard routes (real-time operations UI)
│   ├── hooks.py                      # PreToolUse & PostToolUse guardrail hooks
│   ├── main.py                       # FastAPI app entry point, Telegram webhook endpoint
│   ├── models.py                     # SQLAlchemy ORM models (products, bills, ledgers, etc.)
│   ├── telegram_bridge.py            # Telegram message handler, update deduplicator, media downloader
│   ├── providers/                    # LLM provider abstraction layer
│   │   ├── base.py                   # Abstract provider interface
│   │   ├── claude.py                 # Claude 3.5 Sonnet provider implementation
│   │   └── gemini.py                 # Google Gemini provider implementation
│   └── tools/                        # 31 business tool implementations
│       ├── __init__.py               # Tool registry
│       ├── analytics.py              # daily_close, sales_summary, gst_collected, reorder_suggestions
│       ├── billing.py                # start_bill, add_bill_item, finalize_bill, void_bill, list_bills...
│       ├── credit.py                 # add_customer, add_credit, record_payment, get_customer_balance...
│       ├── documents.py              # generate_invoice_pdf, generate_analysis_deck
│       ├── gst_utils.py              # Decimal-precision GST calculation engine with HSN lookup
│       ├── inventory.py              # find_product, add_product, receive_stock, list_low_stock...
│       ├── preferences.py            # set_preference, get_preference, list_preferences
│       └── vision.py                 # identify_product_from_image (Gemini Vision)
│
├── alembic/                          # Database schema migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py     # Complete initial database schema
│
├── frontend/                         # Web dashboard assets
│   ├── static/                       # CSS, JavaScript, images
│   └── templates/                    # Jinja2 HTML templates
│       ├── dashboard.html            # Real-time operations dashboard
│       └── invoice.html              # GST invoice template (WeasyPrint source)
│
├── scripts/                          # Utility and operations scripts
│   ├── poll_telegram.py              # Long-polling Telegram updates (development mode)
│   ├── seed_data.py                  # Development data seeder
│   ├── deduplicate_products.py       # Product deduplication utility
│   ├── schedule_weekly_deck.py       # Monday morning PPTX analytics scheduler
│   ├── verify_capabilities.py        # 11-capability verification suite
│   ├── verify_hard_parts.py          # 9-hard-problem verification suite
│   └── verify_stretch_goals.py       # 8-stretch-goal verification suite
│
├── tests/                            # pytest test suite (49 tests)
│   ├── conftest.py                   # Shared fixtures and mock setup
│   ├── test_gst.py                   # GST calculation engine tests (12 tests)
│   ├── test_billing.py               # Draft & finalize billing tests (9 tests)
│   ├── test_concurrency.py           # Concurrency / oversell stress tests (8 tests)
│   ├── test_credit.py                # Customer credit ledger tests (7 tests)
│   ├── test_documents.py             # PDF and PPTX generation tests (6 tests)
│   ├── test_idempotency.py           # Duplicate rejection tests (4 tests)
│   ├── test_preferences.py           # Preference persistence tests (3 tests)
│   └── test_provider_routing.py      # Provider routing and fallback tests
│
├── skills/                           # Agent skill documentation (SKILL.md per domain)
│   ├── analytics/SKILL.md
│   ├── billing/SKILL.md
│   ├── documents/SKILL.md
│   ├── inventory/SKILL.md
│   ├── khata/SKILL.md
│   ├── preferences/SKILL.md
│   └── vision/SKILL.md
│
├── screenshort_video and document/   # All visual documentation and sample outputs
│   ├── 1.png – 11.png               # Feature screenshots
│   ├── invoice_707AF91A.pdf          # Sample GST invoice
│   ├── invoice_CDB2640F.pdf          # Sample GST invoice (with breakdown)
│   ├── analysis_today_2026-09-08.pptx # Auto-generated analytics deck
│   └── README.md                     # Media directory index
│
├── docs_output/                      # Runtime-generated invoices & documents (gitignored)
├── .env.example                      # Environment variable template — copy → .env
├── requirements.txt                  # Python package dependencies
├── Dockerfile                        # Container image definition
├── docker-compose.yml                # Multi-service container stack (app + PostgreSQL)
├── alembic.ini                       # Alembic migration configuration
├── pytest.ini                        # pytest configuration
├── run.bat                           # 1-click Windows launcher (PostgreSQL + app + browser)
└── stop.bat                          # Clean Windows service shutdown script
```

---

## ⚡ 11. Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 16
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Google AI Studio key ([aistudio.google.com](https://aistudio.google.com))

---

### Option A: 1-Click Windows Launcher *(Recommended)*

```bat
:: Start PostgreSQL, apply migrations, launch Dashboard + Bot, open browser
run.bat

:: Stop all services cleanly
stop.bat
```

---

### Option B: Docker Compose

```bash
# 1. Copy and fill in your environment variables
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services (app + PostgreSQL)
docker-compose up -d

# 3. Apply database migrations
docker-compose exec app alembic upgrade head
```

---

### Option C: Manual Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/SivaSankar-eLab/Supermarket-Store.git
cd Supermarket-Store

# 2. Create Python virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Open .env and fill in your API keys and database URL

# 5. Start PostgreSQL and apply schema migrations
alembic upgrade head

# 6. Seed development data (optional)
python scripts/seed_data.py

# 7. Launch the application
python run_all.py

# Or start services individually:
# Terminal 1 — FastAPI server + webhook
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Telegram long-polling (dev mode)
python scripts/poll_telegram.py
```

---

## 🔧 12. Environment Variables

Copy `.env.example` → `.env` and fill in your values. **Never commit `.env` to git.**

| Variable | Description | Required |
|:---|:---|:---:|
| `ANTHROPIC_API_KEY` | Claude API key from [console.anthropic.com](https://console.anthropic.com) | ✅ |
| `GEMINI_API_KEY` | Google AI Studio key from [aistudio.google.com](https://aistudio.google.com) | ✅ |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) | ✅ |
| `DATABASE_URL` | PostgreSQL async URL: `postgresql+asyncpg://user:pass@host:5432/dbname` | ✅ |
| `DATABASE_URL_SYNC` | PostgreSQL sync URL: `postgresql://user:pass@host:5432/dbname` | ✅ |
| `SHOP_ID` | UUID for your store (any valid UUID v4) | ✅ |
| `SHOP_NAME` | Your store display name (e.g. "Metro Supermarket") | ✅ |
| `SHOP_OWNER_NAME` | Store owner's name | ✅ |
| `SHOP_GSTIN` | GST Identification Number (appears on invoices) | ✅ |
| `SHOP_ADDRESS` | Store address (appears on PDF invoices) | ✅ |
| `CLAUDE_MODEL` | Claude model ID (default: `claude-3-5-sonnet-20241022`) | ⬜ |
| `GEMINI_MODEL` | Gemini model ID (default: `gemini-flash-lite-latest`) | ⬜ |
| `WEBHOOK_URL` | Public HTTPS URL for Telegram webhook (production only) | ⬜ |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook validation secret (production only) | ⬜ |
| `APP_HOST` | Server bind host (default: `0.0.0.0`) | ⬜ |
| `APP_PORT` | Server bind port (default: `8000`) | ⬜ |
| `APP_ENV` | Runtime environment: `development` or `production` | ⬜ |
| `DOCS_OUTPUT_DIR` | Directory for generated PDF invoices and PPTX files | ⬜ |

> **Security Note**: A `.env.example` template with placeholder values is included. Your real `.env` file is excluded from git via `.gitignore`.

---

## 🧪 13. Testing

```bash
# Run the full 49-test suite
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html

# Verify all 11 core store capabilities
python scripts/verify_capabilities.py

# Verify all 9 architectural hard parts & safety guards
python scripts/verify_hard_parts.py

# Verify all 8 advanced enterprise stretch goals
python scripts/verify_stretch_goals.py
```

### Test Coverage

| Test Suite | # Tests | What's Covered |
|:---|:---:|:---|
| GST Calculation Engine | 12 | Decimal precision, CGST/SGST splits, HSN code lookup, invoice rounding |
| Concurrency / Oversell Guard | 8 | 50-concurrent-request stress test — exactly 20/20 succeed |
| Draft Billing Multi-Turn | 9 | Add / edit / remove / finalize / void full lifecycle |
| Customer Credit Ledger | 7 | Balance computation, payment recording, statement retrieval |
| Document Generation | 6 | PDF invoice rendering, PPTX analytics deck with charts |
| Idempotency & Deduplication | 4 | Duplicate update_id rejection, idempotency_key uniqueness |
| Preferences Persistence | 3 | Cross-session memory (persists across `/new` resets) |
| **Total** | **49** | **All passing ✅** |

---

## 🎬 14. Demo Walkthrough

Test the live bot [`@mykiranastore_bot`](https://t.me/mykiranastore_bot) in this sequence to see all capabilities:

```
1. 📦 Receive Stock
   → "Add 50kg Aashirvaad flour, bought at ₹42 per kg, selling at ₹50"

2. 🧾 Multi-Item Bill with Real-Time Edit
   → "Bill for Ravi: 2kg flour, 1L Saffola oil, 500g Tata salt"
   → "Wait, make it 3kg flour instead of 2"
   → "Also add 1 packet Parle-G biscuits"
   → "Finalize via UPI"

3. ⚡ Oversell Guard (Safety)
   → "Bill 500kg flour for Suresh"
   ← Bot refuses: "Only X kg in stock — cannot oversell"

4. 💳 Customer Credit Ledger Cycle
   → "Sunita took goods worth ₹800 on credit"
   → "Sunita paid ₹500 via UPI today"
   → "What is Sunita's outstanding balance?"

5. 📄 GST-Compliant PDF Invoice
   → "Send me the PDF invoice for Ravi's latest bill"
   ← Bot sends a professional PDF with GSTIN, HSN codes, CGST+SGST breakdown

6. 📊 Executive Analytics Deck
   → "Generate a PowerPoint analysis deck for this week's store performance"
   ← Bot sends a PPTX with bar charts, pie charts, top SKUs

7. 🧠 Preferences & Memory Persistence Across /new
   → "Set default payment method to UPI"
   → "/new"
   → "What is my default payment method?"
   ← "UPI" (remembered across session reset!)

8. 📷 Vision AI Product Identification
   → [Send a product photo]
   ← Bot identifies: "Aashirvaad Atta 5kg — ₹XXX — Barcode: 89XXXXXXXXX"

9. 🔔 Low Stock Alert
   → "Show me all items running low"
   ← List with current stock vs. threshold and reorder suggestions
```

---

## 📜 15. Commit History & Progression

The repository maintains a clean, progressive commit history showing architectural development step-by-step:

```
9353b7f  chore: ignore github setup script in gitignore
b4a37e0  docs: complete README, architecture diagram, screenshots, tests, and skill docs
1e44dc7  feat: Telegram bridge, FastAPI entry point, web dashboard, and scripts
cfef93f  feat: multi-provider agent harness with 31 tools across 6 skill domains
0dffbbd  feat: core database models, config, and Alembic migrations
328acac  feat: initial project scaffold and configuration
```

| Commit | Stage | What Was Built |
|:---|:---|:---|
| `328acac` | Scaffold | Project structure, `.env.example`, `requirements.txt`, `.gitignore`, `Dockerfile`, `docker-compose.yml` |
| `0dffbbd` | Data Layer | SQLAlchemy models for all 8 tables, Alembic migration, PostgreSQL connection pool, config settings |
| `cfef93f` | Intelligence | 31 tools across 7 domains, multi-provider agent harness (Claude + Gemini), GST engine, PreToolUse hooks |
| `1e44dc7` | Interface | Telegram bridge + deduplicator, FastAPI entry point, web dashboard, `run.bat`, `stop.bat`, scripts |
| `b4a37e0` | Documentation | Comprehensive README, architecture diagram, 11 screenshots, PDF invoices, PPTX deck, 49 pytest tests, skill docs |
| `9353b7f` | Housekeeping | Added `github_setup.ps1` to `.gitignore` to prevent accidental credential exposure |

---

## ❓ 16. FAQ

**Q: Does this work for stores outside India?**
> The billing and credit systems are generic. The GST engine is India-specific. You can disable GST slabs and use it as a plain POS agent anywhere.

**Q: Can I use only Gemini without Claude?**
> Yes. The `app/providers/` layer is fully abstracted. Set `ANTHROPIC_API_KEY` to empty and configure Gemini as the primary in `app/agent.py`.

**Q: Is the Telegram bot production-ready?**
> Yes. It uses webhook deduplication, idempotency keys, row-level locking, and has 49 automated tests. It runs at `@mykiranastore_bot`.

**Q: Why PostgreSQL and not SQLite?**
> `SELECT ... FOR UPDATE` row-level locking (which prevents overselling) requires a full RDBMS. SQLite doesn't support this. PostgreSQL 16 is also production-grade and supports `pg_trgm` for fuzzy search.

**Q: Where is the demo video?**
> The demo video (`video.mp4`) is included in [`screenshort_video and document/`](./screenshort_video%20and%20document/) and can be viewed directly from the repository.

**Q: How do I set up a public webhook URL for production?**
> Use `ngrok` for local testing (`ngrok http 8000`) or deploy to any cloud (Railway, Render, GCP, AWS). Set `WEBHOOK_URL` in `.env` to your public HTTPS URL.

---

## 📜 17. License

This project is **private and proprietary**. All rights reserved © 2026 SivaSankar-eLab.

Unauthorized copying, forking, or distribution of this codebase is strictly prohibited without written permission from the project owner.

---

<div align="center">

Built with ❤️ using **Claude Agent SDK** · **Google Gemini** · **PostgreSQL 16** · **Telegram Bot API** · **FastAPI** · **WeasyPrint** · **python-pptx**

⭐ *If this project helped you, give it a star!* ⭐

</div>
