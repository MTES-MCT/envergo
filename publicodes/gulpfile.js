import { src, dest, parallel, series, watch } from 'gulp';
import uglify from 'gulp-uglify';
import rename from 'gulp-rename';
import nodemon from 'gulp-nodemon';

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

// Watch for changes
function watchFiles() {
    watch(paths.publicodes, copyPublicodes);
    watch(paths.js, scripts);
}

// Default task
export default series(parallel(scripts, copyPublicodes), serveNode, watchFiles);
