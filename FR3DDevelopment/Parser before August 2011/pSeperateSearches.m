Filenames = dir(['MotifLibrary' filesep]);
for m = 1:length(Filenames),
    if (length(Filenames(m).name) > 2),
      if (Filenames(m).name(1:2) == 'IL'), 
          keep(m) = 1;
          Filenames(m).name = strrep(Filenames(m).name,'.mat','');
      end
    end 
end
Filenames = Filenames(find(keep));

for i = 1:length(Filenames),
  MN = Filenames(i).name;
  FN = ['MotifLibrary' filesep MN '.mat'];
  fullSearch = load(FN,'Search','-mat');
  [m,n] = size(fullSearch.Search.Candidates);
  for j = 1:m,
      f = fullSearch.Search.Candidates(j,n);           % file numbers of motifs
      Search.Candidates = fullSearch.Search.Candidates(m,:);
      Search.Candidates(n) = 1;
      Search.File = fullSearch.Search.File(f);
      Search.Discrepancy = fullSearch.Search.Discrepancy(f);
      Search.Query = fullSearch.Search.Query;
      Search.origmatfilename = fullSearch.Search.origmatfilename;
      Search.Signature = fullSearch.Search.Signature;
      Search.matfilename = fullSearch.Search.matfilename;
      Search.Truncate = fullSearch.Search.Truncate;
      Search.ownsequencefasta = fullSearch.Search.ownsequencefasta;
      Search.modelfilename = fullSearch.Search.modelfilename;
      oFN = ['MotifLibrary' filesep 'Seperated' filesep MN '_' int2str(j) '.mat'];
      save(oFN,'Search','-mat')
  end
end