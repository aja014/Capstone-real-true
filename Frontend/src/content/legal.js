// Terms of Service and Privacy Policy shown from the Create Account modal (LegalModal.jsx).
// Edit the wording here; **text** is shown in bold. Sections are numbered automatically.

export const TERMS_OF_SERVICE = {
  title: "Terms of Service — FIREMAP (Maagap Insurance, Inc.)",
  effective: "Effective: September 2026",
  sections: [
    {
      heading: "About this system.",
      text: "FIREMAP is an internal system of Maagap Insurance, Inc. for managing policyholder information, quotations, policies, claims, flood-risk mapping, renewals, and risk predictions. It is for authorized Maagap personnel only.",
    },
    {
      heading: "Accounts.",
      text: "Accounts are created by a manager. Each account is for one person only. Do not share your username or password. You are responsible for all activity done under your account. Log out when you leave your device, and change your password right away if you think someone else knows it.",
    },
    {
      heading: "Acceptable use.",
      text: "Use the system only for your work at Maagap. Do not:",
      bullets: [
        "access, copy, or export records you do not need for your work;",
        "share client information with anyone outside the company without authorization;",
        "enter false or misleading information;",
        "try to bypass security, access other users' accounts, or disrupt the system.",
      ],
    },
    {
      heading: "Accuracy of data.",
      text: "Enter and upload information carefully and completely, based on the company's official documents. Review and resolve records flagged as \"Needs Review\".",
    },
    {
      heading: "Predictions are decision support only.",
      text: "Claim Possibility, Risk Assessment, Fraud Warning, flood-risk results, and the Policy Forecast are estimates produced from past data and public hazard maps. They can be wrong. They do not approve, deny, or price any quotation or claim by themselves. Final decisions are always made by authorized Maagap personnel following company procedures.",
    },
    {
      heading: "Confidentiality.",
      text: "Client information in this system is confidential. Your duty to protect it continues even after your account is removed.",
    },
    {
      heading: "Monitoring.",
      text: "Management may review the records in the system to protect client data.",
    },
    {
      heading: "Account removal.",
      text: "When an account is no longer needed, the manager arranges its removal with the system administrator.",
    },
    {
      heading: "Changes.",
      text: "These terms may be updated. Continuing to use the system means you accept the updated terms.",
    },
    {
      heading: "Questions.",
      text: "Contact your manager or the system administrator.",
    },
  ],
};

export const PRIVACY_POLICY = {
  title: "Privacy Policy — FIREMAP (Maagap Insurance, Inc.)",
  effective: "Effective: September 2026",
  sections: [
    {
      heading: "Our commitment.",
      text: "Maagap Insurance, Inc. protects personal information in line with the Data Privacy Act of 2012 (Republic Act No. 10173) and its implementing rules.",
    },
    {
      heading: "Information we process.",
      bullets: [
        "**Policyholders:** name, address, contact numbers, email, civil status, spouse name, employer, TIN, SSS number, and similar details from company forms.",
        "**Insured property and vehicles:** location of risk, survey details, vehicle details, plate and engine/chassis numbers.",
        "**Insurance records:** quotations, policies, renewals, and claims (including claim amounts and investigation results).",
        "**System users:** username, role, and password (stored only in scrambled form, never as plain text).",
      ],
    },
    {
      heading: "Why we use it.",
      text: "To process quotations and policies, handle claims, check flood and storm-surge risk, monitor renewals, estimate claim and fraud risk, and produce management reports.",
    },
    {
      heading: "Who can see it.",
      text: "Only authorized Maagap personnel with an account, based on their role. We do not sell personal information.",
    },
    {
      heading: "Outside services.",
      text: "To find the flood-risk level of an address, the system sends **only the address** (no names or other personal details) to OpenStreetMap's Nominatim geocoding service. Found locations are saved inside the system so the same address is not sent again. Map images are loaded from a map provider when a location is viewed.",
    },
    {
      heading: "Security.",
      text: "Every page requires login. Passwords are scrambled (hashed) and follow a minimum strength rule. Login sessions expire automatically. Deleted business records (clients, policies, claims) are archived first so they can be reviewed.",
    },
    {
      heading: "Keeping records.",
      text: "Records, including archived (deleted) records, are kept for as long as required by insurance, legal and company requirements.",
    },
    {
      heading: "Rights of data subjects.",
      text: "Under the Data Privacy Act, clients have the right to be informed, to access, to correct, and to object, among others. Requests are handled by Maagap following company procedures.",
    },
    {
      heading: "Reporting a problem.",
      text: "If you think client information was shared or accessed without authorization, report it to your manager right away.",
    },
    {
      heading: "Changes.",
      text: "This policy may be updated when the system or the law changes.",
    },
  ],
};
