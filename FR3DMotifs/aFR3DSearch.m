function [Search] = aFR3DSearch(Query,GenericFile)

Filenames = Query.SearchFiles;
Verbose = 0;
MaxNumberOfCandidates = Inf;
% MaxNumberOfCandidates = 1000;

if nargin < 2

    [File,SIndex] = zAddNTData(Filenames,0,[],Verbose);   % load PDB data
    % don't search if there are no nucleotides in the file, otherwise will crash.
    if isempty(File(1).NT)
        Search = [];
        return;
    end
    Query = xConstructQuery(Query, File);

else

    File = GenericFile.File;
    % File(1) - Query File, File(2) - target file
    Query = xConstructQuery(Query,File(1));
    File(1) = [];
    SIndex = 1;

end

Query.Verbose = 0;
fprintf('Query %s\n', Query.Name);

% ------------------------------------------- Calc more distances if needed -

for f=1:length(SIndex),
    i = SIndex(f);
    if isempty(File(i).Distance),
        dmin = 0;
    else
        dmin = ceil(max(max(File(i).Distance)));
    end

    if (ceil(Query.DistCutoff) > dmin) && (File(i).NumNT > 0),
        c = cat(1,File(i).NT(1:File(i).NumNT).Center);
        File(i).Distance = zMutualDistance(c,Query.DistCutoff);
    end
end

% ------------------------------------------- Find candidates ---------------

starttime = cputime;
Candidates = xFindCandidates(File(SIndex),Query,Verbose);  % screen for candidates


if ~isempty(Candidates)                         % some candidate(s) found

    if Query.Geometric > 0
        
        [Discrepancy, Candidates] = xRankCandidates(File(SIndex),Query,Candidates);
        fprintf('Found %d candidates in the desired discrepancy range\n',length(Discrepancy));

        if (Query.ExcludeOverlap > 0) && (~isempty(Discrepancy)) && (Query.NumNT >= 2)

            [Candidates, Discrepancy] = xExcludeOverlap(Candidates,Discrepancy,MaxNumberOfCandidates);
            [Candidates, Discrepancy] = xExcludeRedundantCandidates(File(SIndex),Candidates,Discrepancy);

        end

    elseif Query.NumNT > 2,

        if (Query.ExcludeOverlap > 0)
            [Candidates] = xExcludeRedundantCandidates(File(SIndex),Candidates);
            if Verbose > 0,
                fprintf('Removed candidates from redundant chains, kept %d\n', length(Candidates(:,1)));
            end
        end

        A = [Candidates sum(Candidates')'];        %#ok<UDIM> % compute sum of indices
        N = Query.NumNT;                           % number of nucleotides
        [y,i] = sortrows(A,[N+1 N+2 1:N]);         % sort by file, then this sum
        Candidates = Candidates(i,:);              % put all permutations together
        Discrepancy = (1:length(Candidates(:,1)))';% helps identify candidates
        
    else

        if (Query.ExcludeOverlap > 0)
            [Candidates] = xExcludeRedundantCandidates(File(SIndex),Candidates);
            if Verbose > 0,
                fprintf('Removed candidates from redundant chains, kept %d\n', length(Candidates(:,1)));
            end
        end

        N = Query.NumNT;                           % number of nucleotides
        [y,i] = sortrows(Candidates,[N+1 1 2]);
        Candidates = Candidates(i,:);              % put all permutations together
        Discrepancy = (1:length(Candidates(:,1)))';% helps identify candidates
        
    end

    % -------------------------------------------------- Save results of search

    Search.SaveName    = [datestr(now,31) '-' Query.Name];    
    Search.Query       = Query;
    Search.Filenames   = Filenames;
    Search.TotalTime   = cputime - starttime;
    Search.Date        = Search.SaveName(1:10);
    Search.Time        = Search.SaveName(12:18);
    Search.Candidates  = Candidates;
    Search.Discrepancy = Discrepancy;

    Search = xAddFiletoSearch(File(SIndex),Search);

    if ~isempty(Search.Candidates)    
        if isfield(Query,'SaveDir')
            outdir = Query.SaveDir;
        else
            outdir = 'tempResults';
        end

        if ~exist(outdir,'dir')
            mkdir(outdir);
        end
        save([outdir filesep Query.Name], 'Search');
    end

    
else
    
    Search.Query = Query;

end

end


% drawnow


% if isfield(Query,'Verbose') && isequal(Query.Verbose,1)
%     disp(Query);
% else

% end
%     Search.SaveName    = strrep(Search.SaveName,' ','_');
%     Search.SaveName    = strrep(Search.SaveName,':','_');
%     Search.SaveName    = strrep(Search.SaveName,'<','_');
%     Search.SaveName    = strrep(Search.SaveName,'>','_');
%     Search.SaveName    = strrep(Search.SaveName,'?','_');
%     Search.SaveName    = strrep(Search.SaveName,'*','_');
%     Search.SaveName    = strrep(Search.SaveName,'&','_');


    % ------------------------------------------------ Display results
%     if Verbose > 0
%         fprintf('Entire search took %8.4f seconds, or %8.4f minutes\n', (cputime-starttime), (cputime-starttime)/60);
%     end
% 
%     if Verbose > 0
%         xListCandidates(Search,20,1); %outputs the first 20 candidates
%     end


% Search = struct;
% if isfield(Query,'Description'),
%     fprintf(' %s\n', Query.Description);
% else
%     fprintf('\n');
% end


%             if Verbose > 0,
%                 fprintf('Removed highly overlapping candidates, kept %d\n', length(Candidates(:,1)));
%             end


%             tt = cputime;

            %     fprintf('%d candidates after xExcludeRedundantCandidates, time %8.6f\n', length(Discrepancy),(cputime-tt));

%             tt = cputime;

            %     fprintf('%d candidates after xExcludeOverlap, time %8.6f\n', length(Discrepancy),(cputime-tt));

%             tt = cputime;

            %      [C, D] = xReduceOverlap(Candidates,Discrepancy);


% C1 = xFindCandidates_old(File(SIndex),Query,Verbose);  % screen for candidates
% if ~isequal(sortrows(Candidates),sortrows(C1))
%     keyboard;
% end


% else
% %    File = GenericFile.SmallFile;
% %    SIndex = GenericFile.SmallQIndex;
%     File = GenericFile.File;
%     SIndex = GenericFile.QIndex;
% end
% % ------------------------------------------- Store actual filenames
% %                                             rather than list name(s)
%
% clear Filenames;
%
% for i = 1:length(SIndex),
%   Filenames{i} = File(SIndex(i)).Filename;
% end
%
% %------------------------------------------- Construct details of search
%  if isfield(Query,'Filename'),                % if query motif is from a file
%   [File,QIndex] = zAddNTData(Query.Filename,0,File);
%   Query = xConstructQuery(Query,File(QIndex)); % preliminary calculations
%  else
%   Query = xConstructQuery(Query);              % preliminary calculations
%  end


