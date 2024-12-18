import http from 'http';
import { evaluateQuality } from './src/hedges/quality.js';

const port = 4000;

const server = http.createServer((req, res) => {
    if (req.method === 'POST') {
        if (req.url === '/hedges/quality/') {
            let body = '';
            req.on('data', chunk => {
                body += chunk.toString();
            });
            req.on('end', () => {
                const data = JSON.parse(body);
                const result = evaluateQuality(data);
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                res.end(JSON.stringify(result));
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

server.listen(port, () => {
    console.log(`Server is running on port: ${port}`);
});
