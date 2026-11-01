---
title: "SmartPOS"
summary: "Multi-tenant point-of-sale and inventory backend in C# and ASP.NET Core, with end-of-day ledger reconciliation running in the background and no overselling when cashiers check out at the same time."
context: "Personal project · C# / .NET 9"
period: "2026"
role: "Solo developer"
tech: ["C#", ".NET 9", "ASP.NET Core Web API", "EF Core", "Dapper", "PostgreSQL", "Redis", "Hangfire", "MediatR (CQRS)", "FluentValidation", "xUnit", "Testcontainers", "Docker", "HTML/CSS/JavaScript"]
links:
  - label: "Source on GitHub"
    url: "https://github.com/Nasju666/Multi-Tenant-Smart-POS-Inventory-Engine-with-Background-Ledger-Sync"
order: 2
images:
  - src: "smartpos-1.webp"
    alt: "SmartPOS checkout terminal: product catalog with stock badges and the current order with VAT breakdown"
    w: 1600
    h: 1000
  - src: "smartpos-2.webp"
    alt: "Sales and ledger dashboard: today's revenue, peak hours chart, top products and the sealed ledger archive"
    w: 1600
    h: 1863
  - src: "smartpos-3.webp"
    alt: "Concurrency lab: a race test where one cashier gets 201 Created and the other 409 Conflict, and a burst test throttled with 429"
    w: 1600
    h: 1000
  - src: "smartpos-4.webp"
    alt: "Digital thermal receipt after a completed payment"
    w: 1600
    h: 1000
  - src: "smartpos-5.webp"
    alt: "End-of-day reconciliation certificate for the Cebu IT Park branch"
    w: 1600
    h: 1000
  - src: "smartpos-6.webp"
    alt: "Inventory with low-stock alerts and stock level bars"
    w: 1600
    h: 1046
  - src: "smartpos-7.webp"
    alt: "SmartPOS checkout on a phone"
    w: 780
    h: 1688
---
A backend for retail chains where several businesses (tenants) share one system, built with **C# on .NET 9** using Clean Architecture (Domain, Application, Infrastructure, API).

- **Tenant isolation:** middleware reads the tenant on every request, and EF Core global query filters scope every query to it, so one business can never see another's data.
- **No overselling:** products carry a row-version concurrency token. When two cashiers sell the last unit at the same moment, one checkout succeeds and the other gets a clean `409 Conflict`.
- **CQRS with MediatR:** thin controllers send commands and queries; a FluentValidation pipeline checks every command before the business logic runs.
- **EF Core for writes, Dapper for reads:** transactions go through EF Core, while dashboards and reports use fast Dapper SQL queries.
- **Background ledger sync:** Hangfire seals each store's sales at the end of its own local business day (store time zones, e.g. Asia/Manila).
- **Rate limiting:** per-tenant checkout limits with ASP.NET Core's rate limiter, returning `429` with `Retry-After` under load.
- **Tested:** xUnit unit tests for the domain and handlers, plus integration tests against a real PostgreSQL in Testcontainers.

It ships with a POS terminal and dashboard in plain HTML, CSS and JavaScript, served by ASP.NET Core: checkout with peso pricing and 12% VAT, receipts, inventory, sales analytics and a "concurrency lab" that shows the overselling protection live. Runs with one `docker compose up`.
