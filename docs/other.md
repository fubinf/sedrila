# Minor additional commands

Besides the support for users in different roles, 
there are a few much smaller commands.


## `server`: Personal webserver for authors

`sedrila` provides a very simple built-in web server.
Its only purpose is serving the files built by `sedrila author`
so that authors can review the results of their work.

The server will respond only to requests directed at `localhost`,
so you cannot use this for any purpose beyond personal use.
Which is good, because the server (which uses Python's `http.server.ThreadingHTTPServer`)
is simplistic and is neither fast enough nor (in particular) secure enough nor flexible enough
to be used as a public production webserver.

Call it as follows:  
`sedrila server [--quiet|-q] port mydir`,  
for example  
`sedrila server -q 8099 build &`.

This will serve all files in subdirectory `build` (into which presumably a prior
`sedrila author build` has put the generated files).
The server will respond on port 8099, so you can reach it via
`http://localhost:8099/`.
Due to the `&`, it will run in the background.

The `-q` (or `--quiet`) will suppress the one line of logging output that the webserver
would otherwise produce for each request and which will hardly ever be of interest
unless you want to redirect them into some file for keeping tabs on what you do.
Logging output goes to standard error.
