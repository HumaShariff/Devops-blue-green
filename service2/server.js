const express = require('express');
const fs = require('fs');
const axios = require('axios');

const app = express();

function uptime_hours(){
  try{
    const u = fs.readFileSync('/proc/uptime', 'utf8').trim().split(/\s+/)[0];
    return parseFloat(u)/3600.0;
  }catch(e){
    return 0;
  }
}

function free_disk_mb(){
  try{
    const out = require('child_process').execSync("df / --output=avail -m | tail -1").toString().trim();
    return out.split(/\s+/)[0];
  }catch(e){
    return '0';
  }
}

function timestamp_iso_utc(){
  return new Date().toISOString().replace(/\.\d+Z$/, 'Z');
}

app.get('/status', async (req,res) => {
  const ts = timestamp_iso_utc();
  const hours = uptime_hours();
  const free_mb = free_disk_mb();
  const record = `${ts}: uptime ${hours.toFixed(2)} hours, free disk in root: ${free_mb} MBytes`;

  // POST to storage container
  try {
    await axios.post('http://storage:5000/log', record, { headers: { 'Content-Type': 'text/plain' }, timeout: 5000 });
  } catch(e) {
    console.error("POST to storage failed:", e.message || e);
  }

  res.type('text/plain').send(record);
});

app.listen(5000, '0.0.0.0', () => console.log('Service2 (Node) listening on 5000'));

