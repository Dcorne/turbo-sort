# Turbo Sort 3.0 beta

**Turbo Sort sorts your movie and TV files into folders and gives them clearer names.**

For example, it can turn this:
The.Office.S06E03.mkv


into this:
TV
└── The Office
    └── Season 6
        └── The Office S06 E03.mkv

It works from the names of your files. It does not look up movies or shows online.
**Nothing moves until you tell it to.** Your first run shows you what it plans to do.
Start with copies of a few files before using your whole collection.

## 1. Getting setup

You need:

- Python version 3.11 or newer installed on your computer.
- The Turbo Sort.py and IF YOU WANT turbo setup.py ( Setup can make and input where your source folder is so you don't need to do any surgery in the actual sort.py files. If you want to go ahead, Just wanted to make something that takes any possible errors on your hands off the main file and gives you ease of changing file paths if needed.
- Some finished movie or TV downloads to organize.

Python is the software that runs Turbo Sort. You do not need to know how to write Python code.

Decide which three folders you want to use:

| Folder              What it is for                 | Example 
_____________________________________________________________________________
| Starting folder    |Files waiting to be sorted     | `C:\Downloads\Completed` 
| TV folder          | Where sorted TV episodes go   | `C:\Media\TV` 
| Movies folder      | Where sorted movies go        | `C:\Media\Movies` 

These are examples. Use your own folders.
**Keep the three folders separate.** Do not put one inside another.
Wait for downloads to finish, and stop any programs that might still be changing those files.

## 2. Open a command window

Turbo Sort runs using typed instructions called **commands**.
On Windows:

1. Open the folder containing `turbo_sort.py` and `turbo_setup.py`.
2. Click the address bar at the top of the folder window.
3. Type `powershell` and press **Enter**.

A command window opens. You can paste the commands below into it and press **Enter** to run them.
To check whether Python is ready, enter:

python --version


You should see a version number of **3.11 or higher**.
If Windows says it cannot find Python, or opens the Microsoft Store instead, Python is not ready to use through this command. Finish installing or setting up Python before continuing.

## 3. Run the guided setup

Enter:
python turbo_setup.py

The setup asks which folders you want to use and how you want files and folders named.
For example, it may ask whether season three should look like:

- `Season 3`
- `S03`

It shows you an example of your choices.
When you finish, it saves your settings in a file called `config.toml`. If that file already exists, setup saves the previous version as `config.toml.bak`.
**Setup only saves settings. It does not move your videos.**

## 4. Preview the changes

Enter:
python turbo_sort.py --config config.toml

Turbo Sort shows what it plans to do.

**This is only a preview. It does not change your files or folders.**

Read the results. Check that:

- Shows and movies have the right names.
- TV episodes have the right season and episode numbers.
- Files are going into the folders you intended.

A message marked `SKIP` means Turbo Sort is leaving that file alone. Check the reason beside it.

If something looks wrong, run setup again and then repeat the preview.

## 5. Move the files

When you are happy with the preview, enter:

python turbo_sort.py --config config.toml --apply

**The extra word `--apply` tells Turbo Sort to actually move the files.**

It copies each video to its new location, checks that the copy matches, and then removes the original.
There is no automatic undo. Check the preview carefully.

## Why did it skip a file?

Some common reasons:

- **The file is too small.** By default, Turbo Sort ignores videos smaller than about 100 MB.
- **The name is unclear.** It needs enough information to recognize the movie or episode.
- **The destination already has that filename.** Turbo Sort will not replace an existing file.
- **Two files would get the same destination name.** Turbo Sort skips both.
- **The file type is unsupported.**

For testing with small videos, preview using:

python turbo_sort.py --config config.toml --min-size-mb 0

To move those small videos after checking the preview, use:


python turbo_sort.py --config config.toml --min-size-mb 0 --apply

## What filenames does it understand?

These are examples of names it recognizes:

| Filename                 |Meaning 
--------------------------------------------------------------
| `The.Office.S06E03.mkv`  | The Office, season 6, episode 3 
| `Show.S01E01E02.mkv`     | One file containing episodes 1 and 2 
| `Show.10x101.mkv`        | Season 10, episode 101 
| `News.2024.03.05.mkv`    | An episode dated March 5, 2024 
| `Movie.2020.2160p.mkv`   | A movie named “Movie,” with year 2020 

Spaces, dots, and underscores can separate words.

Names such as `Show.101.mkv` or `Movie.1080p.mkv` are too unclear and are skipped.

Episode ranges such as `S01E01-E03` are also skipped. Multiple episodes must be listed explicitly, such as `S01E01E02E03`.
Because Turbo Sort reads filenames without checking online, it can make mistakes. For example, it may mistake a year in a title for the movie’s release year.

## Which file types work?

**Videos:** MKV, AVI, MP4, TS, M4V, MOV, and WEBM.
**Accompanying files:** SRT, ASS, SSA, VTT, SUB, IDX, and SRR.

Matching subtitle files move after their video moves successfully. Language labels such as `.en.srt` and `.fr.forced.srt` are kept.

## Things to know before sorting a large collection

- **Leave enough free space.** Turbo Sort temporarily needs room for another full copy of the file it is moving.
- **Existing files are not overwritten.**
- **Run only one copy of Turbo Sort at a time.**
- **Do not download into or edit files while they are being sorted.**
- **Check skipped files and errors.** Finishing a run does not necessarily mean every file was sorted.
- **A subtitle can fail even if its video moves successfully.** Check for subtitles left in the starting folder.
- **If removing the original fails, you may have two copies.**
- **If the program is interrupted, it may leave a temporary file with `.turbo-sort-` in its name and `.partial` at the end.** Check it before deciding what to do with it.

## Already using Turbo Sort 2.3?

Version 3 uses a different settings system.

Run the guided setup to create a new configuration. Do not copy your old settings into the Python program.
Preview is now the default. You must add `--apply` to move files.
Several older options, including overwriting files and deleting leftover files, have been removed.

## Credits and license

Based on Michael Riha’s Turbo Sort v2.3.
Licensed under GPL-3.0-or-later. See `LICENSE.txt`.

For testing details and known technical limits, see `BETA_REPORT.md`.
