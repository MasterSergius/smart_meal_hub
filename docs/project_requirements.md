# Software Requirements Specification (SRS)
## Project: Smart Meal Planning & Grocery Hub ("SmartMeal Hub")

---

## 1. General Project Description
**SmartMeal Hub** is a web service designed for automated balanced meal planning for the week, grocery cart optimization, and home pantry inventory management. The service targets a broad audience (non-tech users) and solves the daily household problem of *"What to cook today?"*, while minimizing food waste and unnecessary grocery shopping expenses.

---

## 2. User Roles & Access (Actors & Auth)
* **Anonymous User:**
  * View public recipes and explore platform features.
  * Register and authenticate within the system.
* **Authorized User (Single / Family Profile):**
  * Manage personal and family preferences, allergies, and dietary restrictions.
  * Manage a virtual "pantry" inventory (available ingredients).
  * Generate, manually edit, and save weekly menus.
  * Build optimized shopping lists.

---

## 3. Functional Requirements

### 3.1. Menu Generation Engine
* **FR-1.1 (Automated Weekly Diet):** The system must automatically generate a 7-day menu (breakfast, lunch, dinner) taking into account:
  * The user's chosen diet (balanced, keto, low-calorie, vegetarian, etc.).
  * Regional and seasonal factors (availability of seasonal vegetables and fruits).
  * Personal stop-lists (allergen ingredients or products excluded by the user).
* **FR-1.2 (Manual Customization):** Users must be able to replace any dish in the generated menu with an alternative in one click.
* **FR-1.3 (Dynamic Portion Scaling):** Changing the number of consumers must automatically recalculate ingredient quantities in recipes and the final shopping list.

### 3.2. Smart Grocery & Fridge Matcher Module
* **FR-2.1 (Pantry Cleanup Mode):** Matching recipes that overlap as much as possible with the ingredients currently available in the user's virtual fridge.
* **FR-2.2 (Minimal Restock Mode):** An algorithm that selects a combination of dishes utilizing maximum existing ingredients while requiring the minimum purchase of missing items.
* **FR-2.3 (Ingredient Normalization & Aggregation):** Combining ingredients from 5-7 selected recipes into a single grocery list featuring:
  * Converting various units of measurement (cloves, grams, milliliters, pieces) into a unified standard.
  * Grouping items by supermarket categories (vegetables, dairy products, groceries, meat, etc.).

---

## 4. Non-Functional Requirements
* **NFR-1 (Performance):** Generating a weekly menu factoring in all filters and diets must not exceed **2 seconds**.
* **NFR-2 (Scalability):** The architecture must be built on microservices, enabling independent scaling of pantry-matching algorithms and the core backend.
* **NFR-3 (Cloud Readiness):** Full containerization via **Docker** and deployment readiness in an **AWS** environment (ECS/Fargate, RDS PostgreSQL, Redis for caching).

---

## 5. Development Roadmap (Video Series Plan)
1. **Stage 0:** Architecture design and database modeling.
2. **Stage 1:** Development of the core user service and recipe catalog.
3. **Stage 2:** Implementation of the menu generation engine and dietary filters.
4. **Stage 3:** Creation of ingredient normalization and dual-mode pantry-matching algorithms.
5. **Stage 4:** Containerization, CI/CD setup, and deployment to AWS.
