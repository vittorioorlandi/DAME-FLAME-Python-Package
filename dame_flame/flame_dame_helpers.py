# -*- coding: utf-8 -*-
"""Helper functions for the flame_algorithm.py and dame_algorithm.py files"""

# author: Neha Gupta, Duke University
# Copyright Duke University 2020
# License: MIT

import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score

from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error

from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer  

def verbose_output(iteration_number, num_matched_groups, num_unmatched_t,
                   num_unmatched, orig_len_df_all, tot_treated, pe,
                   prev_iter_num_unmatched, curr_covar_set):
    
    print("Iteration number: ", iteration_number)
    print("\tNumber of matched groups formed in total: ", num_matched_groups)
    print("\tUnmatched treated units: ", num_unmatched_t, "out of a total of ",
          tot_treated, "treated units")
    print("\tUnmatched control units: ", num_unmatched-num_unmatched_t,
          "out of a total of ", orig_len_df_all-tot_treated, "control units")
    print("\tPredictive error of covariates chosen this iteration: ", pe)
    print("\tNumber of matches made in this iteration: ", 
          prev_iter_num_unmatched - num_unmatched)
    print("\tNumber of matches made so far: ", 
          orig_len_df_all - num_unmatched)
    print("\tIn this iteration, the covariates dropped are: ", curr_covar_set)
    

def compute_bf(matched_rows, treatment_column_name, df_unmatched):
    '''
    Helper function to compute the balancing factor
    '''
    
    mg_treated = matched_rows[treatment_column_name].sum()
    mg_control = len(matched_rows) - mg_treated
    available_treated = df_unmatched[treatment_column_name].sum()
    available_control = len(df_unmatched) - available_treated
    
    if (available_treated != 0 and available_control != 0):
        return mg_treated/available_treated + mg_control/available_control
    elif (available_treated == 0):
        return mg_control/available_control
    elif (available_control == 0):
        return mg_treated/available_treated
    

def find_pe_for_covar_set(df_holdout, treatment_column_name, 
                          outcome_column_name, s, adaptive_weights,
                          alpha_given):
    '''
    this is a helper function to decide_drop that will find pe of a given s
    '''
    # The iteration and mean of array is only used when doing MICE on holdout
    pe_array = []
    for i in range(len(df_holdout)):
        
        
        X_treated, X_control, Y_treated, Y_control = separate_dfs(
            df_holdout[i], treatment_column_name, outcome_column_name, s)
    
        # error check. If this is true, we stop matching.
        if type(X_treated) == bool:
            return False
        
        if adaptive_weights == "ridge" or adaptive_weights == "ridgeCV":
            clf = Ridge(alpha=alpha_given)
        elif adaptive_weights == "decisiontree" or adaptive_weights == "decisiontreeCV":
            clf = DecisionTreeRegressor()
        else:
            return False
        
        if adaptive_weights == "ridge" or adaptive_weights == "decisiontree":
        
            # Calculate treated MSE
            clf.fit(X_treated, Y_treated) 
            predicted = clf.predict(X_treated)
            MSE_treated = mean_squared_error(Y_treated, predicted)
            
            # Calculate control MSE
            clf.fit(X_control, Y_control) 
            predicted = clf.predict(X_control)
            MSE_control = mean_squared_error(Y_control, predicted)
                
        else:
            # calculate MSE via cross validation. 
            MSE_treated = -1*np.mean(cross_val_score(clf, X_treated, Y_treated,
                                                     scoring='neg_mean_squared_error',
                                                     cv=5))
            MSE_control = -1*np.mean(cross_val_score(clf, X_control, Y_control,
                                                     scoring='neg_mean_squared_error',
                                                     cv=5))
            
        pe_array.append(MSE_treated + MSE_control)

    PE = np.mean(pe_array)
    return PE

def create_mice_dfs(df_holdout, num_imputes, outcome_col_name):
    '''
    This creates num_imputes number of imputed datasets
    '''
    df_holdout_array = []
    for i in range(num_imputes):
        imp = IterativeImputer(max_iter=10, random_state=i, 
                               estimator=DecisionTreeRegressor())
        imp.fit(df_holdout)
        tmp_df = pd.DataFrame(data=np.round(imp.transform(df_holdout)), 
                                             columns=df_holdout.columns, 
                                             index=df_holdout.index)
        
        # convert floats to ints because MICE creates floats
        cols = list(tmp_df.columns)
        cols.remove(outcome_col_name)
        tmp_df[cols] = tmp_df[cols].astype('int64')
        df_holdout_array.append(tmp_df)
        
    return df_holdout_array
    
def separate_dfs(df_holdout, treatment_col_name, outcome_col_name,
                       covs_include):
    """
    This function serves to create the control/treatment dfs for use 
    in the decide_drop functions in flame and in dame.
    """
    #X-treated is the df that has rows where treated col = 1 and
    # all cols except: outcome/treated/the covs being dropped
    X_treated = df_holdout.loc[df_holdout[treatment_col_name]==1, 
                       df_holdout.columns.difference(
                               [outcome_col_name, 
                                treatment_col_name] + list(covs_include))]

    #X-control is the df that has rows where treated col = 0 and
    # all cols except: outcome/treated/the covs being dropped
    X_control = df_holdout.loc[df_holdout[treatment_col_name]==0, 
                       df_holdout.columns.difference(
                               [outcome_col_name, 
                                treatment_col_name] + list(covs_include))]

    Y_treated = df_holdout.loc[df_holdout[treatment_col_name]==1, 
                               outcome_col_name]
    
    Y_control = df_holdout.loc[df_holdout[treatment_col_name]==0, 
                               outcome_col_name]
    
    # error check. If this is true, we stop matching. 
    if (len(X_treated)==0 or len(X_control) == 0 or \
        len(Y_treated) == 0 or len(Y_control) ==0 or \
        len(X_treated.columns) == 0 or len(X_control.columns) == 0):
        return False, False, False, False
    
    return X_treated, X_control, Y_treated, Y_control
