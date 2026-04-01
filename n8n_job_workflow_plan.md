# n8n Automated Job Outreach Pipeline Plan

## 1. Architectural Overview

The objective is to build a fully automated, stateful, and highly personalized job application and outreach engine using **n8n**. The pipeline will discover new AI Engineering / SWE-adjacent roles, identify key decision-makers (Hiring Managers, internal recruiters, VP/Directors of Engineering), dynamically tailor your resume/portfolio to the specific role and company, and orchestrate a multi-touch email campaign using rotated Gmail accounts.

**Core Components:**
- **Orchestration:** n8n (can run locally, on an affordable VPS, or n8n Cloud).
- **Database (State & Idempotency):** Supabase (PostgreSQL). We can spin up a separate project or schema inside the existing Project Nexus Supabase.
- **Job/Lead Sourcing:** Apollo.io API (preferred for stable B2B search/emails) or Apify/Proxycurl (for live LinkedIn scraping). 
- **AI Brain:** OpenAI API (GPT-4o-mini) for ultra-cheap, reliable email generation based on job requirements and your CV.
- **Delivery Engine:** Google Workspace / Gmail APIs with rotating credentials.

---

## 2. Database Design (Supabase)

To maintain idempotency (never email the same person twice, never process the same job twice) and track follow-ups, we need three core tables. Using a hashing strategy ensures we avoid duplicates even if the same job is posted slightly differently.

```sql
-- Table 1: job_postings
CREATE TABLE job_postings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash TEXT UNIQUE NOT NULL, -- SHA-256 of (Company Name + Job Title)
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    source_url TEXT,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 2: contacts
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    title TEXT,
    company_id UUID REFERENCES job_postings(id),
    linkedin_url TEXT,
    enriched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 3: outreach_campaigns
CREATE TABLE outreach_campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID REFERENCES contacts(id),
    job_id UUID REFERENCES job_postings(id),
    sender_account TEXT, -- Which Gmail account was used (e.g., account1@domain.com)
    stage VARCHAR(50) DEFAULT 'pending', -- pending, email1_sent, email2_sent, email3_sent, replied, bounced
    thread_id TEXT, -- To reuse the same email thread for follow-ups
    last_contact_date TIMESTAMP WITH TIME ZONE,
    email_draft_1 TEXT,
    email_draft_2 TEXT,
    email_draft_3 TEXT
);
```

---

## 3. Workflow 1: Discovery & Tailoring (Runs Daily)

**Step 1. Trigger & Radial Search State:** 
- A **Cron Node** runs every morning at 9:00 AM.
- Read "last_search_location" from a global n8n variable or a config table. Start with `Detroit, MI`, then bump the radius by 10 miles each day, or move to the next target city (e.g., `Chicago`, `Ann Arbor`, `Remote`).

**Step 2. Fetch Jobs (Apollo.io or Proxycurl):**
- Use the **HTTP Request Node** to search for job postings matching "AI Engineer", "Applied AI", "Machine Learning Engineer". 
- Generate a `content_hash` string (`hash(Company + Title)`).

**Step 3. Idempotency Check:**
- Use the **Supabase Node** (Read). Does `content_hash` exist in `job_postings`? 
- **IF Node**: If Yes -> Stop branch. If No -> Insert job into DB.

**Step 4. Contact Enrichment (Finding the Hiring Manager):**
- For each new job, query the Apollo.io API (or Hunter.io) targeting the same company domain for titles like: `Technical Recruiter`, `Talent Acquisition`, `Engineering Manager`, `VP of Engineering`, `CTO`.
- Grab the 1-2 most relevant contacts and their verified emails.
- Insert to `contacts` table (on conflict do nothing to maintain idempotency).

**Step 5. AI Tailoring Engine (LLM):**
- Use the **OpenAI Node** configured with `gpt-4o-mini`. 
- **System Prompt Format**: "You are writing a cold outreach email for Vibhor. You have his CV/Portfolio. The target is {Contact First Name}, {Title} at {Company}. Here is the Job Description: {Job Description}."
- Generate three outputs in JSON format: `email_1`, `follow_up_2`, `follow_up_3`.
- The outputs should be deeply tailored. E.g., if the job asks for PyTorch and RAG, the LLM heavily centers your work on Project Nexus and RAG architecture.
- Insert generated drafts and "pending" status into `outreach_campaigns` table.

---

## 4. Workflow 2: Sending Engine (Runs Daily, Separated for Rate Limits)

**Step 1. Fetch Pending / Follow-up Tasks:**
- **Supabase Node** queries `outreach_campaigns`:
  - Fetch 50-100 rows where `stage = 'pending'`.
  - Fetch rows where `stage = 'email1_sent'` and `last_contact_date < NOW() - interval '2 days'`.
  - Fetch rows where `stage = 'email2_sent'` and `last_contact_date < NOW() - interval '2 days'`.

**Step 2. Send Email & Rotate Accounts:**
- Pass the dataset into a **Split In Batches Node**.
- To rotate Gmail accounts, use a math expression based on the row index (e.g., `{{ $position % 3 }}`). Depending on the result, route to a different **Gmail Node** (each authenticated with a different App Password or OAuth token).
- *Thread Idempotency*: If sending a follow-up, ensure the Gmail node is mapped to "Reply" and provided the exact `thread_id` saved from Email 1. This ensures follow-ups group natively in the recipient's inbox.

**Step 3. Update State:**
- Mark as `email1_sent` (or `email2_sent`), update `last_contact_date`, and save the Gmail `thread_id` back to Supabase.

---

## 5. Cost Analysis & Optimization

To achieve this at the absolute lowest cost possible without sacrificing quality:

| Component | Optimized Recommendation | Estimated Monthly Cost |
| :--- | :--- | :--- |
| **n8n Orchestration** | Self-host n8n on a VPS (Hetzner, DigitalOcean, or Render). | ~$5 to $7 / mo |
| **Database** | Supabase free tier (up to 500MB is massive for text data). You can add a schema to the existing Project Nexus DB. | $0 / mo |
| **LLM (Tailoring)** | **GPT-4o-mini**. At $0.15/1M input tokens, processing 3000 tokens of CV + Job Desc for 100 leads/day will cost pennies. | < $1 / mo |
| **Email Accounts** | Google Workspace (Business Starter) for 2-3 custom domains (e.g., `@vibhorkashmira.com`, `@vibhor.ai`). | $18 / mo ($6 per seat) |
| **Data / Scraping** | Apollo.io's "Basic" plan offers unlimited email credits for basic usage and sufficient export credits for $49/mo. Alternatively, Apify pay-as-you-go scrapers. | ~$49 / mo |
| **Total Estimated Cost** | **Highly optimized, professional scale pipeline.** | **~$75 / month** |

### Pro Tips for Delivery & Anti-Spam (Very Important):
1. **Never send 100 emails at once:** Space them out. Use n8n's **Wait Node** or Cron scheduling to send 1 email every 5-10 minutes across the accounts.
2. **Setup DMARC/SPF/DKIM:** For whichever domains you buy, use Cloudflare to easily set up email authentication, otherwise you will land in spam instantly.
3. **Opt-out Mechanism:** In the configuration, allow the LLM to gently add a "P.S. if you are not the right person for this, please let me know."
4. **Bounces & Replies (Bonus Step):** Route your Gmail inbox to a webhook or simple n8n email trigger snippet to automatically mark rows in Supabase as `replied` or `bounced` so the automated follow-up halts immediately if they respond.
