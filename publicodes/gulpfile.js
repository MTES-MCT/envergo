import { src, dest, parallel, series } from 'gulp';
import uglify from 'gulp-uglify';
import rename from 'gulp-rename';
import nodemon from 'gulp-nodemon';
import { spawn } from 'child_process';

// Paths configuration
const paths = {
    js: './src/**/*.js',
    publicodes: './src/**/*.publicodes',
    dist: './dist/'
};

// Minify JavaScript files
function scripts() {
    return src(paths.js)
        .pipe(uglify())
        .pipe(rename({ suffix: '.min' }))
        .pipe(dest(paths.dist));
}

// Copy publicodes files
function copyPublicodes() {
    return src(paths.publicodes)
        .pipe(dest(paths.dist));
}

// Serve Node.js application
function serveNode(cb) {
    const server = spawn('node', ['index.js'], { stdio: 'inherit' });
    server.on('close', (code) => {
        console.log(`Server process exited with code ${code}`);
        cb();
    });
}

// Watch Node.js application
function watchNode(cb) {
    let started = false;
    return nodemon({
        script: 'index.js',
        watch: ['index.js', 'src/**/*.js', 'src/**/*.publicodes']
    }).on('start', function () {
        if (!started) {
            cb();
            started = true;
        }
    });
}

// Default task
export default series(parallel(scripts, copyPublicodes), serveNode);

export const watch = series(parallel(scripts, copyPublicodes), watchNode);
