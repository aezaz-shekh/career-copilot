/**
 * Curated, static learning roadmaps shown instantly when a catalog card is
 * clicked (no model call). Each roadmap is a list of sections; each item is a
 * topic name, optionally paired with a short note: `['Topic', 'why it matters']`.
 *
 * These are the "browse" experience. The AI-personalised roadmap (skill-gap from
 * the user's own resume) remains available separately on the Roadmap page.
 */

export const STATIC_ROADMAPS = {
  // ---------------------------------------------------------------- ROLES ----
  'Frontend Developer': {
    kind: 'role',
    summary: 'Build accessible, responsive user interfaces for the web.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['HTML5 & semantic markup', 'structure pages so they are accessible and SEO-friendly'],
          ['CSS: box model, flexbox, grid', 'the core of every layout'],
          ['Responsive design & media queries', 'mobile-first, works on every screen'],
          ['JavaScript fundamentals', 'types, functions, DOM, events'],
          ['Git & GitHub basics'],
        ],
      },
      {
        title: 'Core skills',
        items: [
          ['A framework: React (recommended)', 'components, props, state, hooks'],
          ['Client-side routing'],
          ['Fetching data (fetch / axios)', 'talk to REST APIs'],
          ['State management', 'context, then a library only if needed'],
          ['Package managers & bundlers (npm, Vite)'],
        ],
      },
      {
        title: 'Tooling & quality',
        items: [
          ['A CSS approach: Tailwind or CSS modules'],
          ['Component testing (Vitest / Testing Library)'],
          ['Accessibility (ARIA, keyboard nav)', 'a differentiator freshers often miss'],
          ['Browser dev tools & debugging'],
          ['Performance basics (lazy loading, images)'],
        ],
      },
      {
        title: 'Job-ready',
        items: [
          ['Build 2-3 polished portfolio projects'],
          ['Deploy to Netlify / Vercel / GitHub Pages'],
          ['TypeScript basics', 'increasingly expected'],
          ['Read and use a design system'],
        ],
      },
    ],
  },

  'Backend Developer': {
    kind: 'role',
    summary: 'Build reliable server-side services, APIs and data layers.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['A language: Python, Java or Node.js'],
          ['HTTP, REST and status codes'],
          ['JSON and request/response basics'],
          ['Git & GitHub'],
          ['Command line & Linux basics'],
        ],
      },
      {
        title: 'Core backend',
        items: [
          ['A web framework (FastAPI / Spring Boot / Express)'],
          ['Designing REST APIs', 'resources, verbs, versioning'],
          ['Relational databases & SQL'],
          ['An ORM (SQLAlchemy / Hibernate / Prisma)'],
          ['Authentication & authorization (JWT, sessions)'],
        ],
      },
      {
        title: 'Data & reliability',
        items: [
          ['Database design & normalization'],
          ['Indexing & query optimization'],
          ['Caching basics (Redis)'],
          ['Error handling & structured logging'],
          ['Automated testing (unit + integration)'],
        ],
      },
      {
        title: 'Deploy & scale',
        items: [
          ['Docker & containers'],
          ['Environment config & secrets'],
          ['CI/CD basics (GitHub Actions)'],
          ['Cloud basics (one provider)'],
          ['Message queues (intro)'],
        ],
      },
    ],
  },

  'Full Stack Developer': {
    kind: 'role',
    summary: 'Own a feature end to end — UI, API and database.',
    sections: [
      {
        title: 'Frontend base',
        items: [
          ['HTML, CSS, JavaScript'],
          ['React (components, hooks, routing)'],
          ['Calling APIs and handling loading/errors'],
        ],
      },
      {
        title: 'Backend base',
        items: [
          ['A backend framework (Node/Express or FastAPI)'],
          ['REST API design'],
          ['SQL + an ORM'],
          ['Auth (JWT / sessions)'],
        ],
      },
      {
        title: 'Connect it',
        items: [
          ['CORS, environment variables'],
          ['End-to-end a full feature (form → API → DB → UI)'],
          ['Validation on both client and server'],
        ],
      },
      {
        title: 'Ship it',
        items: [
          ['Git workflow & pull requests'],
          ['Docker for local + deploy'],
          ['Deploy frontend + backend + DB'],
          ['Write a clear README'],
        ],
      },
    ],
  },

  'Data Analyst': {
    kind: 'role',
    summary: 'Turn raw data into clear, decision-ready insights.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Excel / Google Sheets (formulas, pivot tables)'],
          ['Descriptive statistics', 'mean, median, distribution, correlation'],
          ['SQL: SELECT, JOIN, GROUP BY, window functions'],
          ['Data cleaning concepts'],
        ],
      },
      {
        title: 'Analysis toolkit',
        items: [
          ['Python: pandas & numpy'],
          ['Exploratory data analysis (EDA)'],
          ['Data visualization principles'],
          ['A BI tool: Power BI or Tableau'],
        ],
      },
      {
        title: 'Communicate',
        items: [
          ['Building dashboards'],
          ['Storytelling with data'],
          ['Writing clear summaries for non-technical readers'],
        ],
      },
      {
        title: 'Job-ready',
        items: [
          ['2-3 end-to-end analysis projects'],
          ['A public dashboard in your portfolio'],
          ['Basic statistics for A/B testing'],
        ],
      },
    ],
  },

  'Data Engineer': {
    kind: 'role',
    summary: 'Build the pipelines and stores that feed analytics and ML.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Strong SQL'],
          ['Python for data'],
          ['Linux & the command line'],
          ['Git'],
        ],
      },
      {
        title: 'Data stores',
        items: [
          ['Relational databases (PostgreSQL)'],
          ['Data modeling & warehousing (star schema)'],
          ['NoSQL basics'],
          ['Columnar / warehouse concepts'],
        ],
      },
      {
        title: 'Pipelines',
        items: [
          ['ETL vs ELT'],
          ['Batch processing'],
          ['An orchestrator (Airflow, intro)'],
          ['Data quality & validation'],
        ],
      },
      {
        title: 'Scale',
        items: [
          ['Docker'],
          ['Cloud storage & warehouses (one provider)'],
          ['Streaming basics (Kafka, intro)'],
        ],
      },
    ],
  },

  'DevOps Engineer': {
    kind: 'role',
    summary: 'Automate build, deploy and operations for fast, safe releases.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Linux administration'],
          ['Networking basics (DNS, HTTP, TCP/IP)'],
          ['A scripting language (Bash + Python)'],
          ['Git & branching strategies'],
        ],
      },
      {
        title: 'Containers & CI/CD',
        items: [
          ['Docker'],
          ['CI/CD pipelines (GitHub Actions / Jenkins)'],
          ['Artifact & image registries'],
          ['Environment & secrets management'],
        ],
      },
      {
        title: 'Orchestration & cloud',
        items: [
          ['Kubernetes fundamentals'],
          ['One cloud provider (AWS / Azure / GCP)'],
          ['Infrastructure as Code (Terraform)'],
        ],
      },
      {
        title: 'Operate',
        items: [
          ['Monitoring & logging (Prometheus, Grafana)'],
          ['Alerting & on-call basics'],
          ['Security basics (least privilege)'],
        ],
      },
    ],
  },

  'QA Engineer': {
    kind: 'role',
    summary: 'Ensure software quality through structured testing.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['SDLC & STLC'],
          ['Test case design techniques'],
          ['Types of testing (functional, regression, smoke)'],
          ['Defect life cycle & tracking (JIRA)'],
        ],
      },
      {
        title: 'Practical testing',
        items: [
          ['Manual testing of web & mobile apps'],
          ['API testing with Postman'],
          ['SQL to validate data'],
          ['Writing clear bug reports'],
        ],
      },
      {
        title: 'Automation',
        items: [
          ['A language: Java or Python'],
          ['Selenium WebDriver'],
          ['A test framework (TestNG / PyTest)'],
          ['Page Object Model'],
        ],
      },
      {
        title: 'Advance',
        items: [
          ['CI integration of tests'],
          ['Basics of performance testing'],
          ['API automation'],
        ],
      },
    ],
  },

  'Android Developer': {
    kind: 'role',
    summary: 'Build native Android apps with modern tooling.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Kotlin fundamentals'],
          ['Object-oriented programming'],
          ['Android Studio & the build system'],
          ['Activities, fragments, lifecycle'],
        ],
      },
      {
        title: 'Core UI',
        items: [
          ['Jetpack Compose (modern UI)'],
          ['Layouts & navigation'],
          ['Lists & state'],
          ['Material Design'],
        ],
      },
      {
        title: 'Data & logic',
        items: [
          ['Networking (Retrofit)'],
          ['Local storage (Room)'],
          ['Coroutines for async'],
          ['MVVM architecture'],
        ],
      },
      {
        title: 'Ship it',
        items: [
          ['Permissions & app lifecycle'],
          ['Testing basics'],
          ['Publish to the Play Store'],
        ],
      },
    ],
  },

  'AI Engineer': {
    kind: 'role',
    summary: 'Build applications powered by machine learning and LLMs.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Strong Python'],
          ['Math: linear algebra, probability, statistics'],
          ['numpy, pandas'],
          ['Git'],
        ],
      },
      {
        title: 'Machine learning',
        items: [
          ['ML basics (supervised vs unsupervised)'],
          ['scikit-learn'],
          ['Model evaluation & metrics'],
          ['Feature engineering'],
        ],
      },
      {
        title: 'Deep learning & LLMs',
        items: [
          ['Neural network fundamentals'],
          ['PyTorch or TensorFlow'],
          ['Transformers & embeddings (concept)'],
          ['Using LLM APIs / local models (Ollama)'],
          ['Retrieval-Augmented Generation (RAG)'],
        ],
      },
      {
        title: 'Ship it',
        items: [
          ['Serving a model behind an API'],
          ['Prompt engineering & evaluation'],
          ['MLOps basics'],
        ],
      },
    ],
  },

  'Cyber Security Analyst': {
    kind: 'role',
    summary: 'Defend systems by understanding how they are attacked.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Networking (TCP/IP, DNS, HTTP)'],
          ['Operating systems (Linux + Windows)'],
          ['The CIA triad & core security concepts'],
          ['Command line & basic scripting'],
        ],
      },
      {
        title: 'Core security',
        items: [
          ['Cryptography basics'],
          ['Common vulnerabilities (OWASP Top 10)'],
          ['Authentication & access control'],
          ['Security tools (Wireshark, Nmap)'],
        ],
      },
      {
        title: 'Defense',
        items: [
          ['Threat detection & SIEM basics'],
          ['Incident response process'],
          ['Vulnerability assessment'],
        ],
      },
      {
        title: 'Grow',
        items: [
          ['A certification path (CompTIA Security+)'],
          ['Capture-the-flag practice'],
          ['Cloud security basics'],
        ],
      },
    ],
  },

  'Data Scientist': {
    kind: 'role',
    summary: 'Find patterns and build models that drive real decisions.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Python (pandas, numpy)'],
          ['Statistics & probability', 'the backbone of every model'],
          ['SQL for pulling data'],
          ['Data cleaning & wrangling'],
        ],
      },
      {
        title: 'Analysis & visualization',
        items: [
          ['Exploratory data analysis (EDA)'],
          ['matplotlib & seaborn'],
          ['Feature engineering'],
          ['Hypothesis testing & A/B tests'],
        ],
      },
      {
        title: 'Machine learning',
        items: [
          ['scikit-learn'],
          ['Regression & classification'],
          ['Clustering & dimensionality reduction'],
          ['Model evaluation & cross-validation'],
        ],
      },
      {
        title: 'Job-ready',
        items: [
          ['2-3 end-to-end ML projects'],
          ['Share notebooks on GitHub / Kaggle'],
          ['Communicate results clearly'],
        ],
      },
    ],
  },

  'UI/UX Designer': {
    kind: 'role',
    summary: 'Design intuitive, attractive products people love to use.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Design principles', 'hierarchy, contrast, alignment, spacing'],
          ['Colour theory & typography'],
          ['UX vs UI — what each means'],
          ['User-centered design mindset'],
        ],
      },
      {
        title: 'UX process',
        items: [
          ['User research & interviews'],
          ['Personas & user journeys'],
          ['Wireframing & information architecture'],
          ['Usability testing'],
        ],
      },
      {
        title: 'UI & tools',
        items: [
          ['Figma (industry standard)'],
          ['Design systems & components'],
          ['Prototyping & interactions'],
          ['Responsive & mobile design'],
        ],
      },
      {
        title: 'Job-ready',
        items: [
          ['Build a portfolio of 3-4 case studies'],
          ['Show your process, not just screens'],
          ['Basics of HTML/CSS to talk to devs'],
        ],
      },
    ],
  },

  'Cloud Engineer': {
    kind: 'role',
    summary: 'Design, deploy and run applications on the cloud.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Linux & networking basics'],
          ['A scripting language (Python / Bash)'],
          ['Git'],
          ['How the internet & DNS work'],
        ],
      },
      {
        title: 'Core cloud',
        items: [
          ['One provider deeply (AWS / Azure / GCP)'],
          ['Compute, storage & networking services'],
          ['IAM & security basics'],
          ['Managed databases'],
        ],
      },
      {
        title: 'Automate',
        items: [
          ['Infrastructure as Code (Terraform)'],
          ['Docker & containers'],
          ['CI/CD pipelines'],
          ['Monitoring & cost management'],
        ],
      },
      {
        title: 'Grow',
        items: [
          ['Kubernetes basics'],
          ['A cloud certification (e.g. AWS SAA)'],
          ['Serverless (Lambda / Functions)'],
        ],
      },
    ],
  },

  'iOS Developer': {
    kind: 'role',
    summary: 'Build native apps for iPhone and iPad with Swift.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['Swift fundamentals'],
          ['Object-oriented & protocol-oriented basics'],
          ['Xcode & the build system'],
          ['App lifecycle'],
        ],
      },
      {
        title: 'Core UI',
        items: [
          ['SwiftUI (modern UI)'],
          ['Layouts, lists & navigation'],
          ['State & data flow'],
          ['Human Interface Guidelines'],
        ],
      },
      {
        title: 'Data & logic',
        items: [
          ['Networking (URLSession)'],
          ['Local storage (Core Data / SwiftData)'],
          ['Async/await & concurrency'],
          ['MVVM architecture'],
        ],
      },
      {
        title: 'Ship it',
        items: [
          ['Permissions & app services'],
          ['Testing basics'],
          ['Publish to the App Store'],
        ],
      },
    ],
  },

  'Game Developer': {
    kind: 'role',
    summary: 'Build interactive games with an engine and solid fundamentals.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['A language: C# (Unity) or C++ (Unreal)'],
          ['Programming & OOP basics'],
          ['Vectors & basic game math'],
          ['Git for version control'],
        ],
      },
      {
        title: 'Engine core',
        items: [
          ['An engine: Unity (great to start)'],
          ['Scenes, GameObjects & components'],
          ['Physics & collisions'],
          ['Input handling & player movement'],
        ],
      },
      {
        title: 'Build a game',
        items: [
          ['Sprites, animation & audio'],
          ['Game states & UI/menus'],
          ['Save systems'],
          ['Level design basics'],
        ],
      },
      {
        title: 'Ship it',
        items: [
          ['Optimize performance'],
          ['Build for a platform (PC / mobile / WebGL)'],
          ['Publish a small game (itch.io)'],
        ],
      },
    ],
  },

  'Blockchain Developer': {
    kind: 'role',
    summary: 'Build decentralized apps and smart contracts.',
    sections: [
      {
        title: 'Foundations',
        items: [
          ['How blockchains work', 'blocks, hashing, consensus'],
          ['Cryptography basics'],
          ['Wallets, keys & transactions'],
          ['JavaScript & Git'],
        ],
      },
      {
        title: 'Smart contracts',
        items: [
          ['Solidity fundamentals'],
          ['The Ethereum Virtual Machine (EVM)'],
          ['Writing & testing contracts'],
          ['Common security pitfalls'],
        ],
      },
      {
        title: 'Build dApps',
        items: [
          ['Development frameworks (Hardhat / Foundry)'],
          ['Connect a frontend (ethers.js / web3.js)'],
          ['Deploy to a testnet'],
          ['Token standards (ERC-20, ERC-721)'],
        ],
      },
      {
        title: 'Grow',
        items: [
          ['Gas optimization'],
          ['Auditing & best practices'],
          ['Explore L2s & other chains'],
        ],
      },
    ],
  },

  // --------------------------------------------------------------- SKILLS ----
  Python: {
    kind: 'skill',
    summary: 'A versatile language for web, data, automation and AI.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['Variables, types, operators'],
          ['Control flow (if, for, while)'],
          ['Functions & scope'],
          ['Lists, dicts, sets, tuples'],
          ['Strings & f-strings'],
        ],
      },
      {
        title: 'Intermediate',
        items: [
          ['Comprehensions'],
          ['Modules, packages, virtualenv'],
          ['File I/O & JSON'],
          ['Error handling (try/except)'],
          ['Object-oriented programming'],
        ],
      },
      {
        title: 'Advanced',
        items: [
          ['Decorators & generators'],
          ['Type hints'],
          ['Async / await (intro)'],
          ['Testing with pytest'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['A domain: web (FastAPI/Django) or data (pandas)'],
          ['Build a real project'],
          ['Read the standard library docs'],
        ],
      },
    ],
  },

  JavaScript: {
    kind: 'skill',
    summary: 'The language of the web — front and back end.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['Variables (let/const), types'],
          ['Functions & arrow functions'],
          ['Arrays & objects'],
          ['Control flow & loops'],
          ['The DOM & events'],
        ],
      },
      {
        title: 'Intermediate',
        items: [
          ['Array methods (map, filter, reduce)'],
          ['Promises & async/await'],
          ['Fetch API'],
          ['ES modules'],
          ['Scope, closures, this'],
        ],
      },
      {
        title: 'Advanced',
        items: [
          ['Prototypes & classes'],
          ['Error handling'],
          ['Debugging in dev tools'],
          ['A bit of TypeScript'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['A framework (React)'],
          ['Node.js for the backend'],
          ['Build & deploy a project'],
        ],
      },
    ],
  },

  React: {
    kind: 'skill',
    summary: 'The most in-demand UI library for building web apps.',
    sections: [
      {
        title: 'Prerequisites',
        items: [
          ['Solid JavaScript (ES6+)'],
          ['HTML & CSS'],
          ['npm & a bundler (Vite)'],
        ],
      },
      {
        title: 'Core',
        items: [
          ['Components & JSX'],
          ['Props & state'],
          ['Handling events'],
          ['Lists & keys'],
          ['Conditional rendering'],
        ],
      },
      {
        title: 'Hooks & data',
        items: [
          ['useState, useEffect'],
          ['useRef, useMemo, useCallback'],
          ['Fetching data & loading states'],
          ['Client-side routing'],
          ['Context for shared state'],
        ],
      },
      {
        title: 'Level up',
        items: [
          ['Forms & validation'],
          ['Component testing'],
          ['Performance basics'],
          ['Build a full app & deploy'],
        ],
      },
    ],
  },

  SQL: {
    kind: 'skill',
    summary: 'Query and shape data in relational databases.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['SELECT, WHERE, ORDER BY'],
          ['Filtering & operators'],
          ['DISTINCT, LIMIT'],
          ['Basic data types'],
        ],
      },
      {
        title: 'Core',
        items: [
          ['JOINs (inner, left, right)'],
          ['GROUP BY & aggregate functions'],
          ['HAVING'],
          ['Subqueries'],
        ],
      },
      {
        title: 'Advanced',
        items: [
          ['Window functions'],
          ['CTEs (WITH)'],
          ['Indexes & query plans'],
          ['Transactions'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['Database design & normalization'],
          ['Practice on real datasets'],
          ['Optimize slow queries'],
        ],
      },
    ],
  },

  'System Design': {
    kind: 'skill',
    summary: 'Design systems that scale — a key interview topic.',
    sections: [
      {
        title: 'Building blocks',
        items: [
          ['Client-server & HTTP'],
          ['Databases: SQL vs NoSQL'],
          ['Caching'],
          ['Load balancing'],
        ],
      },
      {
        title: 'Concepts',
        items: [
          ['Horizontal vs vertical scaling'],
          ['Consistency, availability, partitioning (CAP)'],
          ['Message queues'],
          ['Rate limiting'],
        ],
      },
      {
        title: 'Data at scale',
        items: [
          ['Database replication & sharding'],
          ['CDNs'],
          ['Search & indexing'],
        ],
      },
      {
        title: 'Practice',
        items: [
          ['Design a URL shortener'],
          ['Design a news feed'],
          ['Estimate capacity & trade-offs'],
        ],
      },
    ],
  },

  'Data Structures & Algorithms': {
    kind: 'skill',
    summary: 'The core of coding interviews — think and solve efficiently.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['Time & space complexity (Big-O)', 'how to reason about efficiency'],
          ['Arrays & strings'],
          ['Hash maps & sets'],
          ['Recursion'],
        ],
      },
      {
        title: 'Core structures',
        items: [
          ['Linked lists'],
          ['Stacks & queues'],
          ['Trees & binary search trees'],
          ['Heaps & priority queues'],
          ['Graphs'],
        ],
      },
      {
        title: 'Key algorithms',
        items: [
          ['Sorting & searching'],
          ['Two pointers & sliding window'],
          ['BFS & DFS'],
          ['Dynamic programming (intro)'],
          ['Greedy & backtracking'],
        ],
      },
      {
        title: 'Practice',
        items: [
          ['Solve problems daily on LeetCode'],
          ['Master patterns, not memorization'],
          ['Do timed mock interviews'],
        ],
      },
    ],
  },

  Java: {
    kind: 'skill',
    summary: 'A powerful OOP language for backend, Android and enterprise.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['Variables, types & operators'],
          ['Control flow & loops'],
          ['Methods & arrays'],
          ['Strings & I/O'],
        ],
      },
      {
        title: 'Object-oriented Java',
        items: [
          ['Classes & objects'],
          ['Inheritance & polymorphism'],
          ['Interfaces & abstraction'],
          ['Encapsulation & access modifiers'],
        ],
      },
      {
        title: 'Core APIs',
        items: [
          ['Collections (List, Map, Set)'],
          ['Generics'],
          ['Exceptions'],
          ['Streams & lambdas'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['Build with Spring Boot (backend)'],
          ['Unit testing with JUnit'],
          ['Build & ship a real project'],
        ],
      },
    ],
  },

  TypeScript: {
    kind: 'skill',
    summary: 'JavaScript with types — safer, more maintainable code.',
    sections: [
      {
        title: 'Prerequisites',
        items: [
          ['Solid JavaScript (ES6+)'],
          ['npm & a bundler'],
        ],
      },
      {
        title: 'Core types',
        items: [
          ['Basic types & type inference'],
          ['Interfaces & type aliases'],
          ['Union & intersection types'],
          ['Functions & typed parameters'],
        ],
      },
      {
        title: 'Level up',
        items: [
          ['Generics'],
          ['Enums & literal types'],
          ['Utility types (Partial, Pick, Record)'],
          ['Narrowing & type guards'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['Use TypeScript with React'],
          ['Type an API layer'],
          ['tsconfig & strict mode'],
        ],
      },
    ],
  },

  'Node.js': {
    kind: 'skill',
    summary: 'Run JavaScript on the server to build fast backends.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['How Node & the event loop work'],
          ['Modules (CommonJS & ES modules)'],
          ['npm & package.json'],
          ['File system & core modules'],
        ],
      },
      {
        title: 'Build APIs',
        items: [
          ['Express fundamentals'],
          ['Routing & middleware'],
          ['REST API design'],
          ['Connecting a database'],
        ],
      },
      {
        title: 'Core skills',
        items: [
          ['Async patterns (promises, async/await)'],
          ['Authentication (JWT)'],
          ['Error handling & validation'],
          ['Environment variables'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['Build a full REST API'],
          ['Add tests'],
          ['Deploy it'],
        ],
      },
    ],
  },

  Docker: {
    kind: 'skill',
    summary: 'Package apps into portable containers that run anywhere.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['What containers solve', '"works on my machine", solved'],
          ['Images vs containers'],
          ['Running & managing containers'],
          ['Docker Hub & registries'],
        ],
      },
      {
        title: 'Build images',
        items: [
          ['Writing a Dockerfile'],
          ['Layers & caching'],
          ['Environment variables & ports'],
          ['Volumes for persistent data'],
        ],
      },
      {
        title: 'Multi-container',
        items: [
          ['Docker Compose'],
          ['Networking between containers'],
          ['A full app: web + DB'],
        ],
      },
      {
        title: 'Apply it',
        items: [
          ['Containerize one of your projects'],
          ['Optimize image size'],
          ['Push to a registry & deploy'],
        ],
      },
    ],
  },

  'Git & GitHub': {
    kind: 'skill',
    summary: 'Version control every developer is expected to know.',
    sections: [
      {
        title: 'Basics',
        items: [
          ['Init, clone, add, commit'],
          ['Staging area & status'],
          ['Viewing history (log, diff)'],
          ['.gitignore'],
        ],
      },
      {
        title: 'Branching',
        items: [
          ['Create & switch branches'],
          ['Merging'],
          ['Resolving merge conflicts'],
          ['A branching workflow'],
        ],
      },
      {
        title: 'Collaborate',
        items: [
          ['Remotes (push, pull, fetch)'],
          ['Pull requests & code review'],
          ['Forking & contributing'],
          ['Writing good commit messages'],
        ],
      },
      {
        title: 'Level up',
        items: [
          ['Rebase vs merge'],
          ['Undoing changes (reset, revert)'],
          ['Tags & releases'],
        ],
      },
    ],
  },

  'Resume Building': {
    kind: 'skill',
    summary: 'Write a sharp, recruiter-ready resume that gets you interviews.',
    sections: [
      {
        title: 'Prepare & target',
        items: [
          ['Pick one target role', 'a focused resume beats a generic one every time'],
          ['Read 3-5 real job descriptions', 'note the exact skills and keywords they repeat'],
          ['List your projects, internships & achievements', 'raw material to pull from'],
          ['Choose a clean single-column template', 'ATS systems parse it reliably'],
        ],
      },
      {
        title: 'Core sections',
        items: [
          ['Contact & links', 'name, phone, email, LinkedIn, GitHub/portfolio'],
          ['A 2-3 line professional summary', 'who you are + your target role + top strength'],
          ['Skills', 'group by category: languages, frameworks, tools'],
          ['Experience / internships', 'company, role, dates, then bullet points'],
          ['Projects', 'crucial for freshers — treat them like work experience'],
          ['Education & certifications'],
        ],
      },
      {
        title: 'Write strong bullets',
        items: [
          ['Start each bullet with an action verb', 'Built, Led, Automated, Improved'],
          ['Show impact, not just tasks', '"cut load time 40%" beats "worked on performance"'],
          ['Quantify with numbers', 'users, %, time saved, scale'],
          ['Use the STAR idea', 'situation → task → action → result, in one line'],
          ['Add the keywords from the job description', 'mirror their exact wording'],
        ],
      },
      {
        title: 'Format for ATS',
        items: [
          ['Keep it to 1 page (freshers)', 'recruiters skim in ~7 seconds'],
          ['No tables, columns, images or text boxes', 'they break automated parsers'],
          ['Standard section headings', '"Experience", "Skills" — not creative labels'],
          ['Consistent dates, fonts & spacing'],
          ['Export as PDF', 'unless the portal explicitly asks for .docx'],
        ],
      },
      {
        title: 'Polish & proofread',
        items: [
          ['Zero spelling / grammar mistakes', 'one typo can cost the interview'],
          ['Consistent verb tense', 'past for old roles, present for current'],
          ['Remove filler & clichés', 'cut "hardworking team player"'],
          ['Get one person to review it'],
          ['Run it through the Resume Review module here', 'AI feedback, fully local'],
        ],
      },
      {
        title: 'Tailor & apply',
        items: [
          ['Make a tailored copy per role', 'reorder skills to match each job'],
          ['Save versions to compare', 'original vs tailored'],
          ['Match your LinkedIn to your resume'],
          ['Track where and when you applied'],
        ],
      },
    ],
  },
}

export const ROLE_ROADMAPS = Object.keys(STATIC_ROADMAPS).filter(
  (k) => STATIC_ROADMAPS[k].kind === 'role',
)
export const SKILL_ROADMAPS = Object.keys(STATIC_ROADMAPS).filter(
  (k) => STATIC_ROADMAPS[k].kind === 'skill',
)

/**
 * Per-roadmap "Essential Tools" chips and a Practice / Build / Deploy footer,
 * shown beneath the roadmap cards (infographic style). Curated, real tools.
 */
export const ROADMAP_EXTRAS = {
  'Frontend Developer': {
    tools: ['HTML5', 'CSS3', 'JavaScript', 'React', 'Tailwind', 'Vite', 'Git', 'GitHub', 'VS Code', 'Figma', 'Chrome DevTools'],
    practice: ['Clone real websites', 'Build 2-3 portfolio projects', 'Deploy on Vercel / Netlify'],
  },
  'Backend Developer': {
    tools: ['Python', 'Node.js', 'FastAPI', 'Express', 'PostgreSQL', 'MongoDB', 'Redis', 'Docker', 'Postman', 'Nginx', 'Linux'],
    practice: ['Build a REST API', 'Add auth + a database', 'Deploy with Docker'],
  },
  'Full Stack Developer': {
    tools: ['React', 'Node.js', 'Express', 'MongoDB', 'PostgreSQL', 'Tailwind', 'Git', 'Docker', 'Postman', 'Vercel'],
    practice: ['Build a full CRUD app', 'Wire frontend + backend + DB', 'Deploy the whole stack'],
  },
  'Data Analyst': {
    tools: ['Excel', 'SQL', 'Python', 'Pandas', 'Power BI', 'Tableau', 'Jupyter', 'Git'],
    practice: ['Clean a messy dataset', 'Build a dashboard', 'Present 3 insights'],
  },
  'Data Engineer': {
    tools: ['Python', 'SQL', 'Apache Spark', 'Airflow', 'Kafka', 'PostgreSQL', 'Docker', 'AWS', 'dbt'],
    practice: ['Build an ETL pipeline', 'Schedule it with Airflow', 'Load into a warehouse'],
  },
  'DevOps Engineer': {
    tools: ['Docker', 'Kubernetes', 'Git', 'GitHub Actions', 'Jenkins', 'Terraform', 'AWS', 'Ansible', 'Prometheus', 'Grafana', 'Linux'],
    practice: ['Containerize an app', 'Set up a CI/CD pipeline', 'Deploy to the cloud'],
  },
  'QA Engineer': {
    tools: ['Selenium', 'Cypress', 'Postman', 'JMeter', 'Jest', 'Git', 'Jira', 'TestRail'],
    practice: ['Write a test plan', 'Automate a test suite', 'Report bugs in Jira'],
  },
  'Android Developer': {
    tools: ['Kotlin', 'Android Studio', 'Jetpack Compose', 'Firebase', 'Retrofit', 'Gradle', 'SQLite', 'Git'],
    practice: ['Build a multi-screen app', 'Connect an API + local DB', 'Publish a release APK'],
  },
  'AI Engineer': {
    tools: ['Python', 'PyTorch', 'TensorFlow', 'scikit-learn', 'Hugging Face', 'Pandas', 'NumPy', 'Jupyter', 'Docker', 'Git'],
    practice: ['Train a model on real data', 'Fine-tune a pretrained model', 'Serve it behind an API'],
  },
  'Cyber Security Analyst': {
    tools: ['Kali Linux', 'Wireshark', 'Nmap', 'Burp Suite', 'Metasploit', 'Splunk', 'Python', 'Git'],
    practice: ['Scan & map a test network', 'Find and report a vulnerability', 'Harden a system'],
  },
  'Data Scientist': {
    tools: ['Python', 'Pandas', 'NumPy', 'scikit-learn', 'Matplotlib', 'Seaborn', 'Jupyter', 'SQL', 'Kaggle', 'Git'],
    practice: ['Enter a Kaggle competition', 'Build an end-to-end ML project', 'Explain your results clearly'],
  },
  'UI/UX Designer': {
    tools: ['Figma', 'Adobe XD', 'Sketch', 'Miro', 'Notion', 'Framer', 'Photoshop'],
    practice: ['Redesign an app you use', 'Build 3 case studies', 'Run a usability test'],
  },
  'Cloud Engineer': {
    tools: ['AWS', 'Azure', 'GCP', 'Terraform', 'Docker', 'Kubernetes', 'Linux', 'Git', 'CloudWatch'],
    practice: ['Deploy an app to the cloud', 'Automate it with Terraform', 'Set up monitoring & alerts'],
  },
  'iOS Developer': {
    tools: ['Swift', 'Xcode', 'SwiftUI', 'Core Data', 'Firebase', 'TestFlight', 'Git'],
    practice: ['Build a multi-screen app', 'Connect an API + local storage', 'Submit to the App Store'],
  },
  'Game Developer': {
    tools: ['Unity', 'C#', 'Unreal Engine', 'Blender', 'Git', 'Visual Studio', 'itch.io'],
    practice: ['Clone a classic game', 'Build a small original game', 'Publish it on itch.io'],
  },
  'Blockchain Developer': {
    tools: ['Solidity', 'Hardhat', 'Foundry', 'ethers.js', 'MetaMask', 'Remix', 'Node.js', 'Git'],
    practice: ['Write & test a smart contract', 'Build a simple dApp', 'Deploy to a testnet'],
  },
  Python: {
    tools: ['Python', 'pip', 'venv', 'Jupyter', 'VS Code', 'Git', 'pytest'],
    practice: ['Automate a boring task', 'Build a small CLI tool', 'Solve 50 practice problems'],
  },
  JavaScript: {
    tools: ['JavaScript', 'Node.js', 'npm', 'VS Code', 'Git', 'Chrome DevTools'],
    practice: ['Build interactive pages', 'Fetch & render API data', 'Ship a small app'],
  },
  React: {
    tools: ['React', 'Vite', 'Tailwind', 'React Router', 'npm', 'Git', 'Vercel'],
    practice: ['Build reusable components', 'Make a data-driven app', 'Deploy on Vercel'],
  },
  SQL: {
    tools: ['PostgreSQL', 'MySQL', 'SQLite', 'DBeaver', 'pgAdmin'],
    practice: ['Model a small schema', 'Write JOIN-heavy queries', 'Optimize with indexes'],
  },
  'System Design': {
    tools: ['Redis', 'Kafka', 'PostgreSQL', 'Nginx', 'Docker', 'AWS', 'Cloudflare'],
    practice: ['Design a URL shortener', 'Design a news feed', 'Estimate scale & trade-offs'],
  },
  'Data Structures & Algorithms': {
    tools: ['LeetCode', 'HackerRank', 'Codeforces', 'GeeksforGeeks', 'Any language', 'A whiteboard'],
    practice: ['Solve 1-2 problems daily', 'Learn one pattern at a time', 'Do timed mock interviews'],
  },
  Java: {
    tools: ['Java (JDK)', 'IntelliJ IDEA', 'Maven', 'Gradle', 'Spring Boot', 'JUnit', 'Git'],
    practice: ['Build a console app', 'Create a Spring Boot API', 'Add unit tests'],
  },
  TypeScript: {
    tools: ['TypeScript', 'Node.js', 'VS Code', 'ESLint', 'npm', 'Git'],
    practice: ['Convert a JS project to TS', 'Type a React app', 'Enable strict mode'],
  },
  'Node.js': {
    tools: ['Node.js', 'Express', 'npm', 'Postman', 'MongoDB', 'PostgreSQL', 'Git'],
    practice: ['Build a REST API', 'Add auth + a database', 'Deploy it live'],
  },
  Docker: {
    tools: ['Docker', 'Docker Compose', 'Docker Hub', 'Dockerfile', 'VS Code', 'Git'],
    practice: ['Containerize an app', 'Run web + DB with Compose', 'Push an image to a registry'],
  },
  'Git & GitHub': {
    tools: ['Git', 'GitHub', 'GitHub Desktop', 'VS Code', 'GitHub Actions'],
    practice: ['Version a project', 'Open a pull request', 'Contribute to open source'],
  },
  'Resume Building': {
    tools: ['Google Docs', 'Overleaf (LaTeX)', 'Canva', 'Jobscan (ATS)', 'Grammarly', 'LinkedIn', 'PDF export'],
    practice: ['Draft one targeted resume', 'Run it through Resume Review', 'Tailor a copy per job'],
  },
}
