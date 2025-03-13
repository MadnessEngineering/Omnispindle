const fs = require('fs');
const path = require('path');

// Read the dashboard JSON file
const dashboardPath = path.join(__dirname, '..', 'dashboard', 'multi_gateway_stats_dashboard.json');
let jsonContent = fs.readFileSync(dashboardPath, 'utf8');

// Fix the regex pattern in Process Gateway Stats function
// We need to double escape the backslashes in the regex pattern
jsonContent = jsonContent.replace(
    /if \(\/\^\\\d\{4\}-\\\d\{2\}-\\\d\{2\}\$\/\.test\(possibleDate\)\)/g,
    'if (/^\\\\d{4}-\\\\d{2}-\\\\d{2}$/.test(possibleDate))'
);

// Write the fixed JSON back
fs.writeFileSync(dashboardPath, jsonContent, 'utf8');

console.log('Fixed regex pattern in dashboard JSON file.'); 
