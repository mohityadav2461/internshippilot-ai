const { buildDraft, STANDARD_FIELDS } = require("./drafts.js");
const profile = {
  full_name: "Test Student", email: "student@example.test", phone: "+91 90000 00000", city: "Kanpur",
  linkedin_url: "", github_url: "https://github.com/student", portfolio_url: "",
  college: "Indian Institute of Technology Kanpur", degree: "BS Economics", graduation_year: 2028,
  skills: ["Python", "Econometrics", "SQL"],
  projects: [{ name: "Demand forecaster", tech: ["Python"], summary: "Forecasts weekly demand with regression models." }],
};
const job = { id: "j", company: "Acme", title: "Data Analyst Intern", location: "Bengaluru, India",
  description: "Work with Python and SQL on forecasting.", role_category: "Analyst" };
const filters = { target_start: "Summer 2027", duration_months: "2-3" };
const out = buildDraft({ profile, job, resume: null, formSchema: null, filters });
const byLabel = Object.fromEntries(out.formAnswers.map(a => [a.label, a]));
const check = (cond, msg) => { if (!cond) { console.error("FAIL:", msg); process.exitCode = 1; } else console.log("ok:", msg); };
check(out.coverLetter.includes("[ADD YOUR OWN MOTIVATION"), "cover letter keeps the motivation placeholder (never generated)");
check(out.coverLetter.includes("Python") && out.coverLetter.includes("Demand forecaster"), "cover letter uses verified skills and project only");
check(!/Google|Microsoft|Stanford|award|published/i.test(out.coverLetter), "cover letter does not invent employers, awards or papers");
check(byLabel["Are you authorized to work in India?"].answer === null && byLabel["Are you authorized to work in India?"].needs_human, "work authorization is never assumed");
check(byLabel["Expected stipend"].answer === null && byLabel["Expected stipend"].needs_human, "expected stipend is never assumed");
check(byLabel["LinkedIn URL"].answer === null && byLabel["LinkedIn URL"].needs_human, "empty profile link is flagged, not invented");
check(byLabel["Full name"].answer === "Test Student" && byLabel["Full name"].source === "profile", "name comes from profile data");
check(byLabel["Resume"].source === "resume_upload" && byLabel["Resume"].needs_human, "resume upload is flagged for the human");
check(out.unknownFields.includes("Expected stipend") && out.unknownFields.includes("Why are you interested in this role?"), "unknownFields lists items needing the human");
check(out.formAnswers.length === STANDARD_FIELDS.length, "standard field set fully covered");
const unknownField = buildDraft({ profile, job, resume: null, filters, formSchema: [{ key: "q1", label: "Describe a time you led a team", type: "textarea", required: true }] });
check(unknownField.formAnswers[0].answer === null && unknownField.formAnswers[0].needs_human, "unrecognised custom question is flagged, not guessed");
