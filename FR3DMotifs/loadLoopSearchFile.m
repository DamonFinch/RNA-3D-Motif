%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Used in conjunction with LoopSearchesLoader.py to import information
% about pairwise all-against-all searches into the database.

% `done` is a comma-separated list of loop searches already in the database
% done = 'IL_157D_001_IL_2XZM_059,IL_157D_001_IL_2XZM_061'

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function [filename, err_msg] = loadLoopSearchFile(input_files, output_folder)

    filename = '';
    err_msg = '';

    try

        filename = fullfile(output_folder, 'SearchResults.csv');
        fid = fopen(filename, 'w');

        files = regexp(input_files, ',', 'split');

        for f = 1:length(files)

            load(files{f});

            disc = Search.Discrepancy(1);
            if disc < 0.001
                disc = 0;
            end

            loop_id1 = Search.Query.Filename;
            loop_id2 = Search.Query.SearchFiles;

            % figure out which pdb file each loop came from
            if f == 1
                load(getPrecomputedDataAddress(loop_id1));
                loop_id1_pdb = File.PDBFilename;
            end
            Search.Query.PDBFilename = loop_id1_pdb;
            load(getPrecomputedDataAddress(loop_id2));
            Search.File.PDBFilename = File.PDBFilename;

            nt_list1 = '';
            for i = 1:length(Search.Query.NT)
                nt_list1 = strcat(nt_list1, ',', Search.Query.NT(i).ID);
            end
            nt_list1 = nt_list1(2:end); % remove the last comma

            nt_list2 = '';
            for i = Search.Candidates(1,1:end-1)
                nt_list2 = strcat(nt_list2, ',', Search.File(i).ID);
            end
            nt_list2 = nt_list2(2:end); % remove the last comma

            fprintf(fid,'"%s","%s","%f","%s","%s"\n', loop_id1, loop_id2, disc, nt_list1, nt_list2);

        end

        fclose(fid);

    catch err
        err_msg = sprintf('Error "%s" on line %i\n', err.message, err.stack.line);
        disp(err_msg);
    end

end