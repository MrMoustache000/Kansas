# project_manager.py
import welly
import os
import pandas as pd
from welly import Project
import glob, sys, io
import ipywidgets as widgets
from tqdm import tqdm
import os
import glob
from welly import Project
from tqdm import tqdm
#from contextlib import redirect_stdout, redirect_stderr
import io
import lasio
import numpy as np
import pandas as pd
import scipy
import matplotlib.pyplot as plt

# region LASIO Supress stdout
# SuppressOutput context manager
class SuppressOutput:
    """A context manager for suppressing stdout and stderr."""
    def __enter__(self):
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.original_stdout = sys.stdout
        self.original_stderr = self.original_stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

# region Project Manager
class ProjectManager:
    def __init__(self, base_directory):
        self.base_directory = base_directory
        self.fields = self.load_fields()
        self.selected_field = None
        self.project = None
        self.unique_curves = []
        self.selected_curves = []
        self.standardized_curve_mapping = {}  
        self.curve_descriptions = []
        self.well_data = {}
        self.field_stats = {}
        self.well_stats = {}

    # region path_las_file_list
    def las_file_list(self):
        """
        Generates a list of paths to LAS files within the selected field directory.

        Args:
            selected_field (str): The name of the selected field.

        Returns:
            list: A list of paths to LAS files.
        """
        field_path = os.path.join(self.base_directory, self.selected_field)
        las_files = [os.path.join(field_path, file) for file in os.listdir(field_path) if file.endswith('.las')]
        return las_files

    # region Load ans Select field
    ########## --- ipwidget - load_and_select_field / widgets.py --- ##########
    def load_fields(self):
        return [name for name in os.listdir(self.base_directory) if os.path.isdir(os.path.join(self.base_directory, name))]

    def load_selected_field(self, progress_callback=None):
        """
        Loads wells for the selected field into a Welly Project.
        
        Returns:
            project: A Welly Project object containing the loaded wells.
        """
        if not self.selected_field:
            raise ValueError("No field selected. Please set the selected_field attribute.")
        
        las_files = self.las_file_list()
        wells = []
        for i, las_file in enumerate(las_files):
            wells.append(welly.Well.from_las(las_file))
            if progress_callback:
                progress_callback(i + 1, len(las_files))
        self.project = welly.Project(wells)
        return self.project

    # region Filtering curves
    ########## --- ipwidget - load_and_select_curves / widgets.py--- ##########
    def get_unique_curves(self):
        """
        Fetches all unique curves available for the current project.
        
        :return: A list of unique curves available in the project
        """
        if not self.project:
            print("Project not loaded. Please load the project first.")
            return []

        unique_curves = set()
        for well in self.project:
            unique_curves.update(well.data.keys())

        self.unique_curves = list(unique_curves)
        return self.unique_curves
    
    def update_selected_curves(self, selected_curves):
        """
        Updates the selected curves based on user input from the widget.
        
        :param selected_curves: A list of curves selected by the user
        """
        self.selected_curves = selected_curves
        # Optionally, filter the project's data to only include selected curves
        self.filter_curves_in_project(self)

    def filter_curves_in_project(self, project):
        """
        Filters the project's well data to only include the selected curves.
        """
        for well in self.project:
            for curve_name in list(well.data.keys()):
                if curve_name not in self.selected_curves:
                    del well.data[curve_name]

        return project
        
    def get_curve_descriptions(self):
        """
        Retrieves descriptions for each unique curve in the project as a dictionary.
        """
        curve_descriptions = {}
        if not self.project:
            print("Project not loaded. Please load the project first.")
            return {}

        for well in self.project:
            lease_name = well.header.loc[well.header['mnemonic'] == 'LEASE', 'value'].values[0]
            header_df = well.header
            curve_info = header_df[header_df['section'] == 'Curves']
            for _, row in curve_info.iterrows():
                curve_name = row['mnemonic']
                description = row['descr'] if row['descr'] else row['value'] if row['value'] else row['unit']
                if curve_name not in curve_descriptions:
                    curve_descriptions[curve_name] = {}
                curve_descriptions[curve_name][lease_name] = description

        self.curve_descriptions = curve_descriptions
        return self.curve_descriptions
    
# region Stadistics
    ########## --- ipwidget - stadistics / widgets.py. --- ##########
    def descriptive_statistics(self):
        """
        Calculates descriptive statistics for the selected curves, for the entire field and each well.
        
        :return: A dictionary containing the calculated statistics
        """
        field_stats = {}
        well_stats = {}

        # Define thresholds or criteria for data filtering
        valid_range = (-1000, 10000)  # Example range, adjust based on your data characteristics

        # Statistics for the entire field
        for curve_name in self.selected_curves:
            # Collecting data from all wells for the curve
            combined_curve_data = np.concatenate([
                well.data[curve_name].values for well in self.project if curve_name in well.data and well.data[curve_name]
            ])
            
            # Filter data based on valid range
            filtered_data = combined_curve_data[(combined_curve_data >= valid_range[0]) & (combined_curve_data <= valid_range[1])]

            # Check if the data is not empty after filtering
            if filtered_data.size > 0:
                field_stats[curve_name] = {
                    'mean': np.mean(filtered_data),
                    'median': np.median(filtered_data),
                    'mode': pd.Series(filtered_data).mode()[0] if not pd.Series(filtered_data).mode().empty else np.nan,
                    'std_dev': np.std(filtered_data),
                    'range': (np.min(filtered_data), np.max(filtered_data)),
                    'variance': np.var(filtered_data),
                    'skewness': scipy.stats.skew(filtered_data),
                    'kurtosis': scipy.stats.kurtosis(filtered_data),
                    'IQR': np.percentile(filtered_data, 75) - np.percentile(filtered_data, 25),
                    'MAD': np.median(np.absolute(filtered_data - np.median(filtered_data))),
                    'CV': np.std(filtered_data) / np.mean(filtered_data) if np.mean(filtered_data) != 0 else np.nan,
                    'percentile25': np.percentile(filtered_data, 25),
                    'percentile75': np.percentile(filtered_data, 75),
                }
            else:
                field_stats[curve_name] = {stat: np.nan for stat in ['mean', 'median', 'mode', 'std_dev', 'range', 'variance', 'skewness', 'kurtosis', 'IQR', 'MAD', 'CV', 'percentile25', 'percentile75']}

        # Statistics for each well
        for well in self.project:
            lease_name = well.header.loc[well.header['mnemonic'] == 'LEASE', 'value'].values[0]
            well_stats[lease_name] = {}
            for curve_name in self.selected_curves:
                if curve_name in well.data and well.data[curve_name]:
                    curve_data = well.data[curve_name].values
                    # Filter data based on valid range
                    filtered_data = curve_data[(curve_data >= valid_range[0]) & (curve_data <= valid_range[1])]
                    if filtered_data.size > 0:
                        well_stats[lease_name][curve_name] = {
                            'mean': np.mean(filtered_data),
                            'median': np.median(filtered_data),
                            'mode': pd.Series(filtered_data).mode()[0] if not pd.Series(filtered_data).mode().empty else np.nan,
                            'std_dev': np.std(filtered_data),
                            'range': (np.min(filtered_data), np.max(filtered_data)),
                            'variance': np.var(filtered_data),
                            'skewness': scipy.stats.skew(filtered_data),
                            'kurtosis': scipy.stats.kurtosis(filtered_data),
                            'IQR': np.percentile(filtered_data, 75) - np.percentile(filtered_data, 25),
                            'MAD': np.median(np.absolute(filtered_data - np.median(filtered_data))),
                            'CV': np.std(filtered_data) / np.mean(filtered_data) if np.mean(filtered_data) != 0 else np.nan,
                            'percentile25': np.percentile(filtered_data, 25),
                            'percentile75': np.percentile(filtered_data, 75),
                        }

        self.field_stats = field_stats
        self.well_stats = well_stats
        return {'Field': field_stats, 'Wells': well_stats}

# def analyze_and_interpolate_completeness_data(project_manager):
#     """
#     Analyzes the completeness of data and interpolates missing data in the selected curves.
#     Additionally, identifies where data is missing.

#         This function uses various techniques to complete missing data, including:
        
#         * Linear interpolation: fills gaps between known values
#         * Polynomial interpolation: fills gaps using a polynomial of a specified degree
#         * Kriging: geostatistical interpolation to predict values at unobserved locations
#         * Linear regression: fills gaps using a linear regression with predictor variables
#         * Mean imputation: fills gaps with the mean value of known data in the same field or well
#         * Mode imputation: fills gaps with the mode value of known data in the same field or well
#         * k-NN (k-Nearest Neighbors) imputation: fills gaps using the k nearest neighbors in feature space
    
#     :return: A dictionary containing completeness metrics, interpolated data, and missing data locations.
#     """
#     results = {}
#     valid_range = (-1000, 200)  # Define valid data range

#     for well in project_manager.project:
#         results[well.name] = {}  # Initialize a dictionary for each well
#         for curve_name in project_manager.selected_curves:
#             if curve_name in well.data:
#                 curve_data = well.data[curve_name].values
#                 x = np.arange(len(curve_data))
                
#                 # Identify valid and missing data
#                 is_valid = (curve_data > valid_range[0]) & (curve_data < valid_range[1])
#                 is_missing = ~is_valid
                
#                 # Store indices of missing data
#                 missing_indices = np.where(is_missing)[0]
                
#                 # Initialize the curve dictionary with missing indices and an empty interpolations dictionary
#                 results[well.name][curve_name] = {
#                     'missing_indices': missing_indices.tolist(),
#                     'interpolations': {}
#                 }
                
#                 # Filter valid data for interpolation
#                 valid_x = x[is_valid]
#                 valid_y = curve_data[is_valid]
                
#                 if len(valid_x) > 1:  # Ensure there are at least two points to interpolate
#                     # Linear interpolation
#                     linear_interpolator = interpolate.interp1d(valid_x, valid_y, bounds_error=False, fill_value="extrapolate")
#                     results[well.name][curve_name]['interpolations']['linear'] = linear_interpolator(x)

#                     # Polynomial interpolation
#                     if len(valid_x) > 3:
#                         poly_interpolator = np.poly1d(np.polyfit(valid_x, valid_y, deg=3))
#                         results[well.name][curve_name]['interpolations']['polynomial'] = poly_interpolator(x)

#                     # Additional interpolation methods can be added here

#     return results




