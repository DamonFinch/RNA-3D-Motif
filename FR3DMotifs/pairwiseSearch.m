function [disc] = pairwiseSearch(file1, file2, exactSizeLimit)

    if nargin < 3
        exactSizeLimit = 0;
    end

    % defer loading loop Precomputed data if not necessary
    if ~ischar(file1)
        [File1, file1] = getNameAndData(file1);
    end
    if ~ischar(file2)
        [File2, file2] = getNameAndData(file2);
    end

    result = getSearchAddress(file1, file2);

    % Parameters structure
    P.Discrepancy   = 1;
    P.Subdir        = fullfile(getSearchFolder, file1, '');
    P.no_candidates = [P.Subdir filesep 'No_candidates.txt'];
    P.maxNtToSearch = 25;
    if ~exist(P.Subdir,'dir'), mkdir(P.Subdir); end

    % look up existing results
    if exist(result,'file')
        try
            load(result);
            disc = Search.Discrepancy(1);
            return;
        catch
            fprintf('Corrupted file %s\n',result);
        end
    else
        P.no_candidates = fullfile(getSearchFolder, file1, 'No_candidates.txt');
        if exist(P.no_candidates, 'file')
        	fid = fopen(P.no_candidates, 'r');
        	no_candidates = textscan(fid, '%s');
        	fclose(fid);
            if ~isempty(find(ismember(no_candidates{1}, file2), 1))
                disc = Inf;
                return;
            end
        end
    end

    % if file1 and file2 are never compared before loop ids
    if ~exist('File1', 'var')
        [File1, file1] = getNameAndData(file1);
    end
    if ~exist('File2', 'var')
        [File2, file2] = getNameAndData(file2);
    end

    % preserved from master branch during merge commit
    % do not search some large loops because they cause Matlab to run out of memory
    % TODO: replace this temporary fix with a more general solution
    %if strcmp(file1, 'IL_1NBS_003') || strcmp(file1, 'IL_1NBS_010') || strcmp(file2, 'IL_1NBS_003') || strcmp(file2, 'IL_1NBS_010')
    %   disc = Inf;
    %   addToNoCandidatesFile(file2, P);
    %   return;
    %end

    % don't analyze huge spurious loops
    if File1.NumNT > P.maxNtToSearch || File2.NumNT > P.maxNtToSearch
        fprintf('Large loop: %s vs %s, %i vs %i\n', file1, file2, File1.NumNT, File2.NumNT);
        if file1 == file2
            P.Discrepancy = 0.1; % can search in itself with very low disc
        else
            addToNoCandidatesFile(file2, P);
            disc = Inf;
            return;
        end
    end

    % don't search large in small
    if ~isSizeCompatible(File1, File2, exactSizeLimit)
        fprintf('Query %s is larger than target %s\n', file1, file2);
        addToNoCandidatesFile(file2, P);
        disc = Inf;
        return;
    end

    % try searching
    Search = struct;

    fprintf('DEBUG(ps): before aSearchFlankingBases\n');

    if aSearchFlankingBases(File1,File2,P) == 1

        fprintf('DEBUG(ps): before aConstructPairwiseSearch\n');
        [Query,S] = aConstructPairwiseSearch(File1, File2, P);
        fprintf('DEBUG(ps): after aConstructPairwiseSearch\n');

        % S.File(1) - query file, S.File(2) - target file.
        if Query.NumNT <= S.File(2).NumNT
            Search = aFR3DSearch(Query,S);
        end
    end

    fprintf('DEBUG(ps): after aSearchFlankingBases\n');

    if ~isfield(Search,'Candidates') || isempty(Search.Candidates)
        addToNoCandidatesFile(file2, P);
        disc = Inf;
    else
        disc = min(Search.Discrepancy);
    end

end

function [searchPossible] = isSizeCompatible(File1, File2, exactSizeLimit)

    if strcmp(File1.Filename, File2.Filename)
        searchPossible = 1;
        return;
    end

    L1 = File1.NumNT;
    B1 = length(aDetectBulgedBases(File1));
    queryEffectiveLength = L1 - B1;


    % check if the query without bulges is <= than the entire target loop
    if queryEffectiveLength <= File2.NumNT
        searchPossible = 1;
        % targetEffectiveLength = File2.NumNT - length(aDetectBulgedBases(File2));
        if exactSizeLimit && (queryEffectiveLength > 20 || File2.NumNT > 20)
            searchPossible = (File2.NumNT - queryEffectiveLength) <= 2;
            if ~searchPossible
                fprintf('Query has size (%i) difference > 2 with target (%i)\n', queryEffectiveLength, File2.NumNT);
            end
        end
    else
        searchPossible = 0;
    end

end

function [] = addToNoCandidatesFile(loop_id, P)

    fid = fopen(P.no_candidates, 'a');
    fprintf(fid,'%s\n', loop_id);
    fclose(fid);

end

function [F, f] = getNameAndData(input_entity)

    if isstruct(input_entity) % assume File structures
        F = input_entity;
        f = input_entity.Filename;
    else % assume loop id
        load(getPrecomputedDataAddress(input_entity));
        F = File;
        f = File.Filename;
    end

end

function [matched] = aSearchFlankingBases(File1, File2, P)

    matched = 0;

    % skip hairpins
    if strcmp(File1.Filename(1:2),'HL')
        matched = 1;
        return;
    end

    % don't search in the same file
    if File1.Filename == File2.Filename
        matched = 1;
        return;
    end

    F = File1;
    [S.File(1), Indices] = leaveOnlyFlankingBases(File1);
    S.File(2)            = leaveOnlyFlankingBases(File2);
    S.QIndex = [1 2];

    Query.Geometric      = 1;
    Query.ExcludeOverlap = 1;
    Query.SaveDir        = pwd;
    Query.SearchFiles    = File2.Filename;
    Query.Filename       = F.Filename;
    Query.ChainList      = {F.NT(Indices).Chain};
    Query.Name           = [File1.Filename '_' File2.Filename];
    Query.NumNT          = length(Indices);
    Query.NTList         = {F.NT(Indices).Number};
    Query.NT             = F.NT(Indices);

    Query.Diagonal(1:Query.NumNT) = {'N'};
    Query.Edges = cell(Query.NumNT, Query.NumNT);
    Query.Edges{1,Query.NumNT} = 'cWW';  % first and last make "outer" cWW
    for kk = 2:2:(Query.NumNT-1),        % loop through all chain breaks
        Query.Edges{kk,kk+1} = 'cWW';
    end

    Query.DiscCutoff = P.Discrepancy;
    Query.RelCutoff  = Query.DiscCutoff;

    fprintf('DEBUG(sfb): before aFR3DSearch\n');
    Search = aFR3DSearch(Query,S);
    fprintf('DEBUG(sfb): after aFR3DSearch\n');

    fprintf('DEBUG(sfb): HERE\n');

    if isfield(Search,'Candidates') && ~isempty(Search.Candidates)
        matched = 1;
        if ismac
            unix(sprintf('rm %s', fullfile(pwd, [Query.Name '.mat'])));
        else
            delete([Query.Name '.mat']); % delete small search
        end
    end

end

function [File, Indices] = leaveOnlyFlankingBases(File)
    % File should contain only nucleotides from an HL, IL, J3, etc.
    chbr = File.chain_breaks;      % already identified strand starts and ends
    Indices = [1 chbr chbr+1 length(File.NT)];  % positions in the file of flanking cWWs
    Indices = sort(Indices);          % put in increasing order, for J3, J4, ...
    fn = fieldnames(File);
    for j = 1:length(fn)              % loop over fields in File data structure, for example Edge, Distance, ...
        [r,c] = size(File.(fn{j}));
        if r == c && r == File.NumNT  % this field is a square matrix, one row/column for each nucleotide
            File.(fn{j}) = File.(fn{j})(Indices, Indices); % pull out submatrix corresponding to Indices
        end
    end
    File.NT = File.NT(Indices);       % keep just the nucleotides of the flanking pairs
    File.NumNT = length(Indices);     % will work for IL, J3, J4, etc.
end

function [Query,S] = aConstructPairwiseSearch(File1, File2, P)

    F = File1;
    S.File = [File1 File2];
    S.QIndex = [1 2];

    if strcmp(F.Filename(1:2),'HL')
        Indices = 1:length(F.NT);     % keep bulged bases in HL comparisons
    else
        bulges = aDetectBulgedBases(F);
        Indices = setdiff(1:length(F.NT),bulges);
    end

    Query.Geometric      = 1;
    Query.ExcludeOverlap = 1;
    Query.SaveDir        = P.Subdir;
    Query.SearchFiles    = File2.Filename;
    Query.Filename       = F.Filename;
    Query.ChainList      = {F.NT(Indices).Chain};
    Query.Name           = [File1.Filename '_' File2.Filename];
    Query.Number         = 1;
    Query.NumNT          = length(Indices);
    Query.NTList         = {F.NT(Indices).Number};
    Query.NT             = F.NT(Indices);
    Query.IndicesManual  = Indices;

    Query.Diagonal(1:Query.NumNT) = {'N'};
    Query.Edges = cell(Query.NumNT,Query.NumNT);

    Query.DiscCutoff = P.Discrepancy;
    Query.RelCutoff = Query.DiscCutoff;

    for i=1:Query.NumNT-1
        Query.Diff{i+1,i} = '>';
    end

    if strcmp(File1.Filename(1:2), 'HL')
        Query.Edges{1, Query.NumNT} = 'cWW flankSS';
    else   % IL, J3, J4, ...
        Query.Edges{1,Query.NumNT} = 'cWW';               % outer cWW basepair

        chainbreak = find(Indices==File1.chain_breaks);   % indices of chain breaks, even after removing bulges
        for kk = 1:length(chainbreak),
            Query.Diff{chainbreak(kk)+1,chainbreak(kk)} = '';      % allow non-increasing nt number at strand breaks
            Query.Edges{chainbreak(kk),chainbreak(kk)+1} = 'cWW';  % cWW interactions across chain breaks
        end

%       Commented out the following lines 2018-11-27 because:
%       A. They would need to be recoded for J3, J4, ...
%       B. Within strands, the first and last nucleotide should already satisfy the BorderSS or flankSS relation
%        if File1.Flank(1,File1.chain_breaks) == 1
%            Query.Edges{1, find(Indices==File1.chain_breaks)} = 'flankSS';
%        end

%        if File1.Flank(File1.chain_breaks+1, end) == 1
%            Query.Edges{find(Indices==File1.chain_breaks+1), end} = 'flankSS';
%        end
    end

end
