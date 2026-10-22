---
title: "White Market"
order: 3
summary: "Blockchain-based peer-to-peer marketplace with escrow, dispute resolution and an admin dashboard."
links:
  - label: "Source on GitHub"
    url: "https://github.com/Nasju666/WhiteMarket"
images:
  - src: "whitemarket-1.webp"
    alt: "White Market landing page: a trading hub for buying and selling with crypto"
    w: 1422
    h: 740
  - src: "whitemarket-2.webp"
    alt: "How it works: connect a wallet, get verified, then browse and place orders"
    w: 1421
    h: 737
  - src: "whitemarket-3.webp"
    alt: "Why White Market: escrow-protected payments, verified sellers and dispute handling"
    w: 1422
    h: 737
  - src: "whitemarket-4.webp"
    alt: "Built for both sides: features for buyers and for sellers"
    w: 1422
    h: 736
  - src: "whitemarket-5.webp"
    alt: "Connecting a MetaMask wallet to White Market"
    w: 1422
    h: 744
  - src: "whitemarket-6.webp"
    alt: "MetaMask signature request to sign in to White Market"
    w: 1422
    h: 743
  - src: "whitemarket-7.webp"
    alt: "Seller dashboard with sales stats and product listings"
    w: 1422
    h: 738
  - src: "whitemarket-8.webp"
    alt: "Order details with an active dispute"
    w: 1422
    h: 737
tech:
  - "Django"
  - "Django REST Framework"
  - "PostgreSQL"
  - "Web3.py"
  - "Solidity"
  - "Hardhat"
  - "MetaMask"
  - "HTML/CSS/JavaScript"
---

White Market solves the trust problem in peer-to-peer trading: buyers pay into a smart-contract escrow, and the money is only released to the seller once the order is completed.

- **Wallet sign-in:** log in with MetaMask by signing a message, with no password.
- **Blockchain escrow:** funds are held by an Ethereum smart contract (Solidity, Hardhat) until delivery is confirmed.
- **Disputes:** buyers and sellers submit evidence, and an admin arbitrates.
- **Seller dashboard:** listings, orders and sales at a glance.
- **KYC and admin monitoring:** verification and real-time transaction tracking for compliance.

The backend is a Django REST API with JWT auth and PostgreSQL, and is covered by 78 automated tests.
