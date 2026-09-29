# The IT Asset Lifecycle Engine: A Technical Deep Dive

This document serves as a comprehensive architectural overview and technical guide to the **District IT Asset and Inventory Management System**.

## Chapter 1: System Overview & Objectives
The system is designed to provide strict governance and auditing over IT assets. It replaces fragmented spreadsheets by offering a centralized platform where IT Support Staff and District Managers can log devices, diagnose hardware, track salvaged components, manage software licenses, and generate compliance reports.

**Core Objectives:**
1. **Device Lifecycle Tracking:** Track hardware from the moment it is received at the IT depot until it is returned to a branch or disposed of.
2. **Component Level Granularity:** Salvage, inventory, and re-install granular components (RAM, HDD, SSD) across different devices.
3. **Strict State Machines:** Enforce logical transitions (e.g., a device cannot be disposed of without first being diagnosed as non-functional and getting a manager's approval).
4. **Auditability:** Keep a historical record of every change made to a device or component.

## Chapter 2: Technology Stack & Architecture
The project follows a classic monolithic Model-View-Template (MVT) architecture, prioritizing rapid development, robust relational data modeling, and server-side rendering.

- **Framework:** Django 5.2.13 (Python)
- **Database:** SQLite (default for development, prepared for PostgreSQL in production)
- **Frontend:** Django Templates with server-side rendering, utilizing `django-crispy-forms`
- **Static Assets:** Managed by WhiteNoise for efficient serving in production
- **Auditing:** `django-simple-history` to automatically track previous versions of model instances

## Chapter 3: Domain Driven Design (The Applications)
The project is logically partitioned into four main Django apps, enforcing a clean separation of concerns:

### 1. `accounts` (Authentication & Authorization)
Uses a custom `User` model inheriting from `AbstractUser`. It implements Role-Based Access Control (RBAC) with two primary roles:
*   **IT_STAFF:** Can create devices, change device statuses, log components, and recommend disposals.
*   **MANAGER:** Primarily acts as an approver (e.g., approving or rejecting disposal recommendations) and consumer of high-level reports.

### 2. `branches` (Organizational Structure)
Maps the physical locations and the people within them.
*   **Branch:** Represents a physical location with a specific Grade (Grade I to IV, Special) and an employee count.
*   **Employee:** Belongs to a branch and can be assigned specific devices.

### 3. `inventory` (The Core Engine)
This is the heart of the system. It handles the complex relationships between hardware, software, and their states.
*   **Device:** The central entity (PCs, Monitors, Printers). It tracks serial numbers, assigned employees, and current status.
*   **StatusHistory:** An append-only ledger tracking every status change (e.g., *Received → Diagnosed Functional*), who made the change, and when.
*   **Component & ComponentUsage:** Allows IT staff to salvage parts (like RAM) from dead machines and install them into other devices to repair them. Tracks installation and removal dates.
*   **DisposalRecommendation:** A workflow model requiring IT staff to justify throwing a device away, which a Manager must explicitly approve or reject.
*   **SoftwareLicense & SoftwareInstallation:** Tracks finite software seats and maps them to specific devices.

### 4. `reports` (Compliance & Analytics)
*   **Report & ReportLine:** Generates aggregated metrics over specific periods (e.g., how many devices a branch sent in vs. how many were maintained or disposed of). Reports go through a Draft/Approved workflow.

## Chapter 4: Business Logic & The State Machine
Instead of scattering business logic in views or models, the project uses a **Service Layer** (`inventory/services.py`). This is a highly commendable architectural pattern that keeps the Django views thin and handles database transactions safely.

**The Device State Machine:**
The lifecycle of a device is strictly governed by a Directed Acyclic Graph (DAG) enforced by the service layer.
1. **RECEIVED**: The entry point.
2. **DIAGNOSED_FUNCTIONAL / DIAGNOSED_NOT_FUNCTIONAL**: IT staff assesses the device.
3. **REPAIRED**: If functional, it is fixed.
4. **RETURNED_TO_BRANCH**: Repaired devices are sent back.
5. **FOR_DISPOSAL**: If non-functional, it is staged for scrap.
6. **DISPOSED**: The terminal state, but *only* achievable if a `DisposalRecommendation` is approved by a Manager.

The `@transaction.atomic` decorator ensures that when a device changes status, the corresponding `StatusHistory` log is written perfectly in sync. If one fails, the whole database transaction rolls back.

## Chapter 5: Workflow Example - "The Dead Laptop"
To illustrate the system in action, here is a typical workflow:
1. **Intake:** A branch sends a broken PC. IT Staff logs it as `RECEIVED`.
2. **Diagnosis:** IT Staff inspects it. The motherboard is fried. They change the status to `DIAGNOSED_NOT_FUNCTIONAL`.
3. **Salvage:** Before scrapping, the IT staff extracts the 8GB RAM stick. They use the system to create a RAM `Component` linked to the dead PC.
4. **Recommendation:** IT Staff creates a `DisposalRecommendation` for the PC.
5. **Manager Review:** The District Manager logs in, sees the pending request, and clicks "Approve". The system safely transitions the PC to `DISPOSED`.
6. **Reincarnation:** Tomorrow, another PC arrives needing RAM. The IT staff uses the system to assign the salvaged RAM to the new PC, saving the district money.
