# InstaCRM Dashboard

**The distributed intelligence hub for stealthy, high-volume Instagram outreach operations.**

![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square)
![Oracle](https://img.shields.io/badge/Database-Oracle%20ATP-F80000?style=flat-square)
![Timezone](https://img.shields.io/badge/Timezone-UTC%20(GMT%2B0)-purple?style=flat-square)

---

## 🚀 Key Features

### 🏛️ Democratic Governance (`/goals`)
- **Propose Targets:** Suggest team-wide or individual performance benchmarks.
- **Safety Protocols:** Set Frequency Caps and Interval Spacing to protect accounts from Instagram's bot detection.
- **Vote & Review:** Collaborative control over the fleet's operational limits.

### 🎭 Multi-Dimensional Fleet Management (`/actors` & `/operators`)
- **Actors View:** Grouped by Instagram handle. See how multiple operators collaborate on a single account.
- **Operators View:** Grouped by team member. Audit individual productivity across their entire portfolio of managed assets.
- **Dual Time-Windows:** Compare "This Week" vs "All Time" (or custom windows) side-by-side on every card.
- **Intelligence Sheets:** Slide-out reports with 14-day velocity charts, lead success distribution, and granular activity logs.

### 🔍 Advanced Leads Explorer (`/leads`)
- **Faceted Search:** Multi-select filters for Status, Operators, and Actors.
- **Interaction History:** See exactly which agents have contacted a specific prospect.
- **Standardized Handles:** Uniform click-to-copy and profile redirection across the entire dashboard.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Core** | Next.js 16 (App Router) + React 19 |
| **Styling** | Tailwind CSS v4 + Shadcn UI |
| **Database** | Oracle ATP (Thin Mode, Direct Connection) |
| **Persistence** | Long-lived Cookies (Display Prefs & Time Standards) |
| **Charts** | Recharts (Hydration-Safe) |

---

## 🗄️ System Architecture

### Database & Time Protocol
The system operates on a **Strict UTC (GMT+0)** protocol. All data moving into the Oracle ATP cloud is converted to UTC, while the UI Layer handles conversion to the user's local timezone using a unified `TimeDisplay` system.

### Checkpoint Sync
To resolve "phantom changes" and alert fatigue, the dashboard uses a **Checkpoint Sync** strategy. Synchronization only triggers a "NEW CHANGES" alert when records are detected with timestamps strictly newer than the last verified checkpoint.

---

## 🛠️ Getting Started

### Installation
```bash
npm install
```

### Environment Setup
Ensure your `.env.local` includes the Oracle connection string and Google OAuth credentials.

### Database Maintenance
- `npm run reset-db`: Factory reset the schema.
- `npm run seed-db`: Populate initial required entities.
- `npx tsx scripts/generate-sample-data.ts`: Generate 200+ realistic targets and 500+ logs for testing.

---

## 📜 Documentation
- [`schema.dbml`](./schema.dbml) - Relational model & constraints.
- [`AI_CONTEXT.md`](./AI_CONTEXT.md) - Deep technical guide for contributors.
- [`project_workflow.drawio`](./project_workflow.drawio) - Architecture & flow diagrams.
