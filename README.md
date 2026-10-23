# SNHU-2026-TERM-C-5-CS-340
## Module 8 Portfolio Submission — Grazioso Salvare Dashboard

This portfolio contains my Project Two animal shelter dashboard and this reflection. The dashboard connects the Austin Animal Center MongoDB data to an interactive table, breed chart, and map. It supports All animals, Water Rescue, Mountain / Wilderness Rescue, and Disaster / Individual Tracking views. Users can filter and sort the table, browse pages, select an animal to map, and reset the view.

### How I write maintainable, readable, and adaptable programs

I organize code by responsibility, use descriptive names, and keep database operations separate from interface behavior. For Project Two, I reused the CRUD Python module from Project One so the dashboard could call a consistent set of database methods instead of repeating connection and query code in callbacks. The dashboard’s query, record normalization, selection, chart, and map logic are distinct, which makes it easier to inspect and change one behavior without rewriting the others. Reusing the module also reduced duplicate code and made database behavior easier to validate. In future projects, I could reuse this CRUD module as a starting point for other Python applications that need controlled access to MongoDB, while adapting its queries and validation to each client’s data and permissions.

### How I approach problems as a computer scientist

I translate client needs into explicit data rules before implementing the interface. For Grazioso Salvare, I represented each rescue category as breed, sex, species, and age constraints, then checked that the dashboard displayed the resulting records and totals. This project required me to consider how a database query and its results would support real user tasks, including filtering, browsing, and locating an individual animal. Compared with assignments focused on a single algorithm or feature, this work connected data modeling, database access, callbacks, and visual feedback into a complete application. For future client requests, I would clarify the users’ goals, identify required fields and edge cases, define measurable acceptance criteria, build small testable components, and verify both normal and empty or invalid results with representative data.

### What computer scientists do and why it matters

Computer scientists turn needs into reliable software and data systems that help people make decisions and complete work. This dashboard can help Grazioso Salvare staff narrow a large shelter dataset to animals matching rescue criteria, compare breed counts, and view an animal’s location. Those capabilities can reduce manual searching and make relevant records easier to review. Clear query rules and visible results also help staff understand how the displayed animals relate to the requested training categories.

### Project Two materials

The final dashboard source, notebook, reusable CRUD module, requirements, dataset, validation results, and screenshots are included with the Project Two files in this repository. The accompanying README Word document describes setup, use, architecture, and verification. The dashboard was verified in the Codio environment with automated behavior checks and live category and reset checks.
