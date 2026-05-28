# FielMedina Backend

FielMedina is a robust backend platform designed to manage and serve local discovery data, including locations, events, hikings, and advertisements. Built with a focus on performance, internationalization, and visual excellence.

---

## 🚀 Tech Stack

- **Framework**: [Django 5.2](https://www.djangoproject.com/)
- **API**: [Strawberry GraphQL](https://strawberry.rocks/) (with [strawberry-graphql-django](https://strawberry-graphql-django.readthedocs.io/))
- **Styling**: [Tailwind CSS 4.x](https://tailwindcss.com/) & [Flowbite](https://flowbite.com/)
- **Database**: PostgreSQL (Production) / SQLite (Development)
- **Features**: 
  - Image Optimization (Pillow)
  - Internationalization (django-modeltranslation)
  - Rich Text Editing (TinyMCE)
  - Geographic Data (django-cities-light)
  - Public Transport Management (Bus/Line Numbers)
  - Hiking Route Ordering & Terminus Geolocation
  - City-based Content Filtering (Locations, Ads, Tips)

---

## 📂 Project Structure

- `core/`: Project configuration, settings, and main URL routing.
- `api/`: GraphQL schema definitions and API logic.
- `guard/`: Main application logic, models (Locations, Events, Ads), and admin views.
- `shared/`: Reusable components, base models (OptimizedImageModel), and utility functions.
- `static/`: Frontend assets (CSS, JS) and Tailwind source files.

---

## 🛠 Getting Started

### Prerequisites
- Python 3.10+
- Node.js (for CSS compilation)

### Installation

1. **Clone and Setup Virtual Env**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file based on the environment requirements (Database URLs, Secret Keys).

3. **Database Setup**:
   ```bash
   python manage.py migrate
   python manage.py cities_light  # Optional: load geographic data
   ```

4. **Frontend Assets**:
   ```bash
   npm install
   npm run build-css
   ```

5. **Run Server**:
   ```bash
   python manage.py runserver
   ```

---

## 📜 The Project Will (Legacy & Maintenance)

> [!NOTE]
> This section acts as a technical "will" for future maintainers to ensure the project's longevity and health.

### 🏛 Architectural Principles
- **API First**: All frontend consumers should prefer the GraphQL endpoint.
- **Image Lifecycle**: Always inherit from `OptimizedImageModel` for new models with images to ensure automatic WebP conversion and resizing.
- **Translation**: New fields requiring multilingual support must be added to `translation.py`.

### ⚠️ Known Technical Debt
- **SQLite vs Postgres**: Some local optimizations are SQLite-specific; verify migrations when moving to RDS/Postgres.
- **Tailwind 4 Migration**: The project uses the latest Tailwind CLI; ensure node dependencies are kept up to date for the JIT engine.

### 🔮 Future Roadmap
- [ ] **Auth Refactor**: Transition to JWT or Strawberry-Django-Auth for better mobile client support.
- [ ] **Caching Layer**: Implement Redis caching for heavy GraphQL queries (Hikings/Locations).
- [ ] **Elasticsearch**: Integration for advanced search capabilities across `cities_light` and local models.

### ☎️ Succession & Support
In the event that this project needs urgent attention and the original developer is unavailable:
- **Primary Contact**: [Aslan / User Details]
- **Infrastructure**: Hosted on [Insert Hosting Details].
- **Deployment**: [Insert CI/CD Details].

---

## 📄 License
Internal / Private - All Rights Reserved.


bunx @tailwindcss/cli -i ./static/src/input.css -o ./static/main.css --watch