# How to handle dependencies

We use [pip-tools](https://github.com/jazzband/pip-tools) to handle project
dependencies.

Read the pip-tools documentation to know how to install new packages or update
existing packages.

DO NOT MANUALLY edit the .txt files, only the .in files.


## How to install a new package

:memo: If you are using docker, you can run these commands in the django container.

```bash
cd requirements
echo "<package name>" >> (base.in|local.in|production.in)
pip-compile base.in
pip-compile local.in
pip-compile production.in
pip-sync (local.txt|production.txt)

# If you are using docker
docker compose build
```

## How to upgrade a single package

```bash
pip-compile -P <package_name> base.in
```

Then run pip-sync / dc build

## How to upgrade ALL packages

```bash
rm *.txt
./compile.sh
```

Then run pip-sync / dc build
