import http from 'http';
import {evaluateQuality} from './src/hedges/quality.js';

const server = http.createServer((req, res) => {

  if (req.method === 'POST') {
    if (req.url === '/hedges/quality/') {
      let body = '';
      req.on('data', chunk => {
        body += chunk.toString();
      });
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const result = evaluateQuality(data);
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify(result));
        } catch (error) {
          res.statusCode = 500;
          res.setHeader('Content-Type', 'text/plain');
          res.end('Internal Server Error\n');
        }
      });
    } else {
      res.statusCode = 404;
      res.setHeader('Content-Type', 'text/plain');
      res.end('Not Found\n');
    }
  } else {
    res.statusCode = 405;
    res.setHeader('Content-Type', 'text/plain');
    res.end('Method Not Allowed\n');
  }
});

server.listen(process.env.PORT || 4000, "0.0.0.0", () => {
  const host = server.address().address
  const port = server.address().port
  console.log('App listening at https://%s:%s', host, port)
});
