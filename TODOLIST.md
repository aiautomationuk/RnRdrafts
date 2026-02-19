# ReadAndReply — SaaS Roadmap

## 1. Web UI for Client Onboarding
- [ ] Login page (Google OAuth already works)
- [ ] Dashboard page showing connected email accounts
- [ ] Form to connect IMAP/SMTP email account
- [ ] Form to connect Gmail account
- [ ] Disconnect/remove account button

## 2. Per-Client AI Assistant Configuration
- [ ] UI to create/edit OpenAI assistant instructions per account
- [ ] Business info fields (name, tone, FAQs, out-of-hours message)
- [ ] Assign assistant to IMAP account from the dashboard
- [ ] Preview/test assistant response before going live

## 3. Admin Dashboard
- [ ] Overview of all active clients
- [ ] Emails processed per client (last 7/30 days)
- [ ] Error log per account (failed sends, IMAP errors)
- [ ] Enable/disable polling per account

## 4. Billing (Stripe)
- [ ] Stripe subscription integration
- [ ] Pricing tiers (e.g. 1 mailbox / 3 mailboxes / unlimited)
- [ ] Usage limits per plan
- [ ] Client billing portal (manage/cancel subscription)

## 5. Dedicated Domain & Branding
- [ ] Move app to readandreply.com (or chosen domain)
- [ ] Update Google OAuth redirect URIs
- [ ] Basic landing page explaining the product
- [ ] Sign-up / onboarding flow for new clients

## 6. Reliability & Monitoring
- [ ] Email alert if polling fails for X consecutive runs
- [ ] Retry logic for failed SMTP sends
- [ ] Log viewer in admin dashboard
- [ ] Health check endpoint already live at /health
