# 🤖 AI Technical Context: InstaCRM Ecosystem

This document provides a deep-dive into the architecture, data flow, and design patterns of the **Insta Outreach Logger (Remastered)** and its **Dashboard (Dashboard)**.

---

## 🎯 1. Core Mission & Problem Statement
Instagram employs sophisticated anti-bot detection. InstaCRM solves this by using a **Zero-Network Footprint** extension that passes data via Native IPC to a local host, which then handles synchronization with the cloud.

---

## 🏗️ 2. System Architecture

### Component Breakdown
| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Desktop Agent** | Python/Chrome | Handles stealthy DM logging via Chrome Native Messaging. |
| **Oracle ATP** | Cloud Core | Central source of truth (GMT+0 UTC). Handles ID generation. |
| **Web Dashboard** | Next.js 16 | The "Dashboard" for Analytics, CRM, and Governance. |

### Data Flow: The "Stealth Bridge"
1. **Capture:** Browser Extension detects a sent DM.
2. **IPC:** Sends JSON packet to local Python Host.
3. **Queue:** Data saved to `LOCAL_DATA.db` (SQLite).
4. **Sync:** Background thread performs **Checkpoint Sync** with Oracle ATP.

---

## 🗄️ 3. Oracle Database Relational Model

The system uses a normalized Oracle schema with strictly enforced **UTC (GMT+0)** timestamps.

### **Core Entities**
*   **`OPERATORS`**: Human team members. Supports real-time status (`online`/`offline`).
*   **`ACTORS`**: Instagram accounts. **Shared Ownership Support:** A single handle (e.g., `fitness_guru`) can have multiple `ACT_ID` entries assigned to different operators.
*   **`TARGETS`**: Prospect leads. Shared across the entire fleet.

### **Logging System**
*   **`EVENT_LOGS`**: Activity stream. Tracks state changes and actions.
    *   Types: `Outreach`, `Change in Tar Info`, `Tar Exception Toggle`, `User`, `System`.
    *   `DETAILS`: JSON-like context.
*   **`OUTREACH_LOGS`**: 1:1 extension for message content.

### **Democratic Governance**
*   **`GOALS`**: Performance targets. Can be scoped to **Team**, **Operator**, or **Actor**.
*   **`RULES`**: Safety protocols (Frequency Caps, Interval Spacing). Prevents bot-flags.

---

## ⚡ 4. Next.js 16 Implementation Details

### **Tech Stack**
- **Framework**: Next.js 16 (App Router) + React 19
- **Database**: Oracle ATP (Direct Connection Mode for Stability)
- **Caching**: React `cache()` + `unstable_cache(tags: ["max"])`
- **Persistence:** Cookie-based storage for `time_display_format`, `actor_display_prefs`, and `operator_display_prefs`.

### **Page Structure**
- **Dashboard (`/`)**: High-level KPIs and live activity feed.
- **Goals (`/goals`)**: Democratic proposal system for success targets and safety rules.
- **Leads (`/leads`)**: CRM table with faceted multi-select filters and "Contacted By" actor tracking.
- **Actors (`/actors`)**: Fleet management grouped by Instagram handle. Features **Dual Time-Window** comparisons.
- **Operators (`/operators`)**: Inverse fleet view grouped by team member. Tracks individual productivity across multiple assets.
- **Logs (`/logs`)**: Full audit trail with deep search and event-type filtering.
- **Settings**: Split into **Profile** (`/settings/profile`) and **Global** (`/settings/global`).

---

## 🛠️ 5. Development & UI Guidelines
- **Time Protocol:** UI must use the `TimeDisplay` component. Data is GMT+0; conversion to local time happens via client-side mounting. Redundant icons are hidden in dense layouts.
- **Interactive Handles:** All Instagram usernames (Actors/Targets) must use the `InstagramUsername` component for standardized hover-to-copy and redirect behaviors.
- **Performance Intel:** Use `ActorPerformanceSheet` and `OperatorPerformanceSheet` for detailed metric drill-downs. These components handle their own data fetching with integrated loading states.
- **Filtering:** Use `FacetedFilter` for all table views to support multi-select.
- **Stability:** Database uses **Direct Connection Mode**. Connection pooling is disabled to prevent memory issues.
- **Security:** Strict bind variable usage (`:params`) for all SQL queries. Type-safety enforced via Zod and strict TypeScript interfaces.
