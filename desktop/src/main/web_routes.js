// Every website page the desktop opens, in one place. The base is config.web_url (production unless
// --web / MINMATAR_WEB_URL says otherwise), never a hard-coded host.
//
// Installed and portable copies keep these paths forever, so they are a contract with the website:
// when a page moves, the website keeps the old path working or redirects it. The backend builds the
// same routes in backend/app/links.py.
const fleet = (web_url, fleet_id, { ended = false } = {}) =>
    `${web_url}/fleets/${ended ? 'history' : 'upcoming'}/${Number(fleet_id)}`

const srp_killmails = web_url => `${web_url}/ships/srp/killmails/`

const campaign = (web_url, slug) => `${web_url}/campaigns/${encodeURIComponent(slug)}`

const intel_scan = (web_url, report_id) => `${web_url}/intel/scans/${encodeURIComponent(report_id)}`

module.exports = { fleet, srp_killmails, campaign, intel_scan }
