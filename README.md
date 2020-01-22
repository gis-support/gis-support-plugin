# gis-support-plugin
Wtyczka GIS Support

Repozytorium prowadzone jest w cyklu Gitflow
https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow
(rozszerzenie `git flow` oczywiście opcjonalne)

Oznacza to kilka rzeczy:
* na codzień commitujemy do gałęzi `develop`, która przechowuje zmiany z nowymi funkcjonalnościami,
modyfikacjami istniejących funkcjonalności itd.
* od gałęzi `develop` mogą wychodzić inne gałęzie (`feature branche`),
do których commitowane są zmiany dla konkretnych funkcjonalności,
np dodanie modułu importu działek z CSV znajdowało by się w gałęzi `import_csv`.
Feature branche dają tą wygodę, że możemy wprowadzać pewne zmiany bez obaw,
że będą konfliktować z innymi, mniejszymi zmianami, dla których nie tworzymy feature brancha.
Po skończeniu pewnej funkcjonalności mergujemy feature branch do `developa`. 
Feature branche mogą być w pełni lokalnie, nie trzeba ich wypychać do zdalnego repozytorium
* gdy mamy gotową nową wersję wtyczki z obecnymi zmianami z `developa`, musimy przygotować wydanie:
mergujemy `develop` do gałęzi `release`,
uzupełniamy tam rzeczy takie jak metadane wtyczki, dokumentację (jeśli kiedykolwiek jakaś będzie)
* gdy chcemy wypuścić wersję mergujemy `release` do `mastera`, tworzymy tag z numerem wersji,
mergujemy z powrotem `master` do `release`, `release` do `developa`, oraz ewentualnie `developa` do feature branchy.
Na końcu wypychamy do zdalnego repozytorium `develop`, `release`, `master` i tagi
* gałąź `hotfix`: wychodzi od `mastera`, commitujemy do niej najważniejsze fixy.
Po zafixowaniu mergujemy `hotfix` do `mastera` i wykonujemy pozostałe kroki z punktu wyżej

Zastosowanie Gitflow można podejrzeć w repozytorium wtyczki ULDK
https://github.com/gis-support/wyszukiwarka-gugik-uldk
