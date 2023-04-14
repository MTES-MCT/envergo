# How to handle dependencies

We use [pip-tools](https://github.com/jazzband/pip-tools) to handle project
dependencies.

Read the pip-tools documentation to know how to install new packages or update
existing packages.

DO NOT MANUALLY edit the .txt files, only the .in files.

## How to install a new package


```bash
cd requirements
echo "<package name>" >> (base.in|local.in|production.in)
pip-compile base.in
pip-compile local.in
pip-compile production.in
pip-sync (local.txt|production.txt)
```

## How to upgrade ALL packages

```bash
rm *.txt
pip-compile base.txt


## How to upgrade ALL packages

```bash
rm *.txt
pip-compile base.txt
./compile.sh
```

Then run pip-sync / dc build
