---
title: "Studio Escrow"
summary: "Booking marketplace for recording studios, built in C# and ASP.NET Core: payments wait in escrow, and an event-driven saga handles every deadline and payout."
context: "Personal project · C# / .NET 9"
period: "2026"
role: "Solo developer"
tech: ["C#", ".NET 9", "ASP.NET Core Web API", "EF Core", "PostgreSQL", "MassTransit", "RabbitMQ", "SignalR", "Hangfire", "Dapper", "MediatR (CQRS)", "JWT auth", "xUnit", "Testcontainers", "Docker", "HTML/CSS/JavaScript"]
links:
  - label: "Source on GitHub"
    url: "https://github.com/Nasju666/event-driven-escrow"
order: 3
images:
  - src: "studio-escrow-1.webp"
    alt: "Book a room: studio rooms with hourly prices and the new booking form"
    w: 1438
    h: 740
  - src: "studio-escrow-2.webp"
    alt: "Buyer's bookings with the money trail from buyer to escrow to provider"
    w: 1410
    h: 741
  - src: "studio-escrow-3.webp"
    alt: "Provider's view of a booking waiting for the buyer's payment"
    w: 1355
    h: 733
  - src: "studio-escrow-4.webp"
    alt: "Opening a dispute, which freezes the money in escrow"
    w: 1341
    h: 739
  - src: "studio-escrow-5.webp"
    alt: "A booking in dispute with the funds frozen in escrow"
    w: 1375
    h: 735
  - src: "studio-escrow-6.webp"
    alt: "Admin disputes page with refund and payout options"
    w: 1354
    h: 738
  - src: "studio-escrow-7.webp"
    alt: "Admin refunding the buyer to settle a dispute"
    w: 1368
    h: 735
---
A two-sided marketplace built with **C# on .NET 9**. Buyers reserve a studio room and pay into escrow, providers accept and mark the session done, and the money is only released when the buyer approves, the inspection window ends without a dispute, or an admin settles a dispute.

- **No double bookings, even under concurrent requests:** a PostgreSQL exclusion constraint guards the time slots. A test fires 12 simultaneous requests and exactly one wins.
- **No lost events:** domain events go into a transactional outbox in the same database transaction (MassTransit with EF Core), then out to RabbitMQ.
- **A saga owns every deadline:** payment windows, provider response windows and the inspection window are scheduled messages, not polling jobs.
- **Money is conserved:** every cent paid into escrow ends up as payout plus platform fee, or goes back to the buyer, through exactly one code path each.
- **Secure by default:** JWT on every endpoint, role policies, ownership checks, and tenant isolation that fails closed.
- **Live updates** with SignalR, nightly reconciliation with Hangfire, and reports with Dapper.
- **Tested:** xUnit unit tests, integration tests on real PostgreSQL (Testcontainers), and saga tests with real timeouts.

Clean Architecture with MediatR, a plain HTML/CSS/JavaScript UI, and one `docker compose up` to run it all.
