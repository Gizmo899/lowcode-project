# Data protection: Job Application Tracker

This is a design proposal, not legal advice and not a finding of compliance. It uses the GDPR, because the app is used in Ireland. The organisation that runs the real service must confirm the lawful basis, who is responsible, the retention periods and the privacy notice before real personal data is used.

Anything marked "(GUESS: please check)" is something I assumed and you have not confirmed. The retention periods below are proposals for you to change.

## Who is responsible

The controller (the organisation that decides why and how the data is used) is whoever runs the service. For a course project this is you or your institution. (GUESS: please check, write the real name here.) There are no processors: the app uses no outside services, sends no emails and shares data with nobody.

## Personal data stored

| Data | Where | Why it is needed |
|---|---|---|
| Full name, email, phone (optional), password hash | user | To sign in, to identify the person, and for the adviser to know whose CV they review |
| Chosen adviser | user | To decide which adviser may see this jobseeker's data |
| CV file, title, file name, upload date | cv | The main service: keeping CVs and getting them reviewed |
| Decision, comment, decision date, deciding adviser | cv | To tell the jobseeker the outcome and why |
| Company, job title, date applied, stage, advert link, notes | job_application | The main service: tracking applications |
| Reminder dates and states | follow_up_reminder | To send follow-up nudges |
| Notification text and dates | notification | To show nudges, digests and CV decisions in the app |
| Run output counts | log file | To show the automations ran. Counts only, no personal data |

The app does not ask for date of birth, home address, nationality, health information, or any employer contact details.

## Lawful basis (the legal reason for using the data)

- **Account, CV storage, CV review by the linked adviser, application tracking, reminders and notifications:** performance of a contract (GDPR Article 6(1)(b)). The person signs up for the service, and this processing is what the service is. If the service is run by a public body as part of a statutory or publicly funded service, the organisation should check public task (Article 6(1)(e)) instead.
- **Security records (the automation log and, if added, failed sign-in records):** legitimate interests (Article 6(1)(f)), to keep the service secure.
- **Consent** is not used as the basis for the core service, because the service cannot work if it is withdrawn.

(GUESS: please check all of this with whoever runs the service.)

## Data minimisation (collect and show only what is needed)

- Phone number is optional. Employer contact details are not stored.
- The adviser sees only their own linked jobseekers: name, email, applications (with their notes) and CVs. The adviser does not see the jobseeker's phone number.
- Because notes can hold personal details, the application form should say that notes are visible to the jobseeker's adviser.
- Other advisers and other jobseekers see nothing about a jobseeker.
- A CV decision notification names the CV and the outcome but does not copy the comment.
- Notification and log text holds the minimum. The log holds counts only.
- The upload page should tell jobseekers not to put ID numbers, photos, health or other sensitive details in a CV, because a CV can contain personal information that the app does not need.

## Retention (how long data is kept)

| Data | How long | How it is removed |
|---|---|---|
| Account, CVs, applications, reminders, notifications | Until the user closes their own account | Deleted at once, together, by the delete rule (Rule 1) |
| Read notifications | 90 days after creation (GUESS: please check) | Deleted by the hourly script's tidy-up |
| Sent or skipped reminders | 90 days after processing (GUESS: please check) | Deleted by the hourly script's tidy-up |
| Log file | 30 days (GUESS: please check) | Old logs removed |
| Backups | Expire after 30 days (GUESS: please check) | Old backups deleted. Deleted accounts can stay in a backup until it expires |

There is no automatic deletion of accounts that are never closed. That would need a "last signed in" date, which is not in the data model. Not decided: whether to add one and delete accounts after a period of inactivity.

## Who can see personal data

| Who | What they can see |
|---|---|
| The jobseeker | All of their own data |
| The jobseeker's linked adviser | The jobseeker's name, email, applications (including notes, read only) and CVs, and can record a decision on a CV. Not the phone number |
| Any other adviser | Nothing about that jobseeker |
| Any other jobseeker | Nothing |
| The operator, or anyone with access to the database file | Everything in the file, including CV files and password hashes. The file is not encrypted by the app, so access to the computer must be limited and the disk encrypted |
| Anyone outside | Nothing. No data is sent anywhere |

## Rights of the people whose data it is

| Right | How the app supports it |
|---|---|
| To be told what happens to their data | A privacy page is needed that covers the points above. The existing app has `privacy.html`. Check it against this document |
| To see their data | Each jobseeker can see all of their own data in the app. A "download my data" export is not built (GUESS: please check if you want it) |
| To correct it | Profile and applications can be edited. A CV can be replaced |
| To have it deleted | Closing the account deletes everything at once (Rule 1). Backups expire as in the table above |
| To object or restrict | By asking the organisation. Not built into the app |
| To complain | To the Data Protection Commission in Ireland |

## Security measures

The measures that protect this data are set out in `docs/threat-analysis.md`: hashed passwords, HTTPS, scoped queries, database rules, a 1 MB file limit, and restricted file access.

## Open points

- Who the controller is, and whether the lawful basis is contract or public task.
- The retention periods above. They are proposals.
- Whether to delete accounts after a period of inactivity.
- Whether the application form should carry a warning that notes are visible to the adviser (recommended).
- Whether to add a "download my data" export.
