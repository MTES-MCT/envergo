import http from 'http';
import {evaluateQuality} from './src/hedges/quality.js';

const port = 4000;

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

server.listen(port, "0.0.0.0", () => {
  console.log(`Server is running on port: ${port}`);
});
