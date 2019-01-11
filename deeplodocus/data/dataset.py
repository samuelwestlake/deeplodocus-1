# Python imports
import pandas as pd
import numpy as np
import mimetypes
import os

# Deeplodocus imports
from deeplodocus.utils.generic_utils import sorted_nicely
from deeplodocus.utils.generic_utils import get_int_or_float
from deeplodocus.utils.generic_utils import is_np_array
from deeplodocus.utils.notification import Notification
from deeplodocus.utils.errors import error_entry_array_size
from deeplodocus.utils.namespace import Namespace

# Deeplodocus flags imports
from deeplodocus.utils.flags.notif import *
from deeplodocus.utils.flags.msg import *
from deeplodocus.utils.flags.lib import *
from deeplodocus.utils.flags.shuffle import *
from deeplodocus.utils.flags.load import *

# Temporary until Namespace fix
import ast


class DatasetLegacy(object):
    """
    AUTHORS:
    --------

    author : Alix Leroy and Samuel Westlake


    DESCRIPTION:
    ------------

    A dataset class to manage the data given by the config files.
    The following class permits :
        - Data checking
        - Smart data loading
        - Data formatting
        - Data transform (through the TransformManager class)


    The dataset is split into 3 subsets :
        - Inputs : Data given as input to the network
        - Labels : Data given as output (ground truth) to the network (optional)
        - Additional data : Data given to the loss function without any comparison with the output (optional)

    The dataset class supports 2 different image processing libraries :
        - PILLOW (fork of PIL) as default
        - OpenCV (usage recommended for efficiency)
    """

    def __init__(self, inputs=None,
                 load_method = DEEP_LOAD_METHOD_MEMORY,
                 labels=None,
                 additional_data=None,
                 number=None,
                 name="Default",
                 use_raw_data=True,
                 transform_manager=None,
                 cv_library=DEEP_LIB_OPENCV):
        """
        AUTHORS:
        --------

        author: Alix Leroy
        author:

        DESCRIPTION:
        ---------

        Initialize the dataset

        PARAMETERS:
        -----------

        :param inputs: A list of input files/folders/list of files/folders
        :param labels: A list of label files/folders/list of files/folders
        :param additional_data: A list of additional data files/folders/list of files/folders
        :param use_raw_data: Boolean : Whether to feed the network with raw data or always apply transforms on it
        :param transform_manager: A transform object
        :param cv_library: The computer vision library to be used for opening and modifying the images data
        :param name: Name of the dataset
        """
        self.inputs = self.__temp_convert_str2dict(self.__check_null_entry(inputs))
        self.labels = self.__temp_convert_str2dict(self.__check_null_entry(labels))
        self.additional_data = self.__temp_convert_str2dict(self.__check_null_entry(additional_data))
        self.load_method = self.__check_load_method(load_method)
        self.number = number
        self.name = name
        self.transform_manager = transform_manager
        self.number_raw_instances = self.__compute_number_raw_instances()
        self.use_raw_data = use_raw_data
        self._data = self.inputs + self.labels + self.additional_data
        self.data = None
        self.cv_library = None
        self.set_cv_library(cv_library)
        self.load()

    def __getitem__(self, index: int):

        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ---------

        Get the instance (input, label, additional_data) corresponding to the given index

        PARAMETERS:
        -----------

        :param index: Int: Index of the instance to load


        RETURN:
        -------

        :return : Loaded and possibly transformed instance to be given to the training
        """
        inputs = []
        labels = []
        additional_data = []
        # Index of the raw data is used only to get the path to original data.
        # Real index is used for data transformation
        index_raw_data = index % self.number_raw_instances
        # If we ask for a not existing index we use the modulo and consider the data to have to be augmented
        if index >= self.number_raw_instances:
            augment = True
        # If we ask for a raw data, augment it only if required by the user
        else:
            augment = not self.use_raw_data
        if index >= self.len_data:
            Notification(DEEP_NOTIF_FATAL, "The given instance index is too high : " + str(index))
        # Extract lists of raw data from the pandas DataFrame for the select index
        if not self.list_labels:
            if not self.list_additional_data:
                inputs = self.data.iloc[index_raw_data]
                # Keep key == 0 else the data frame  also returns the name of the column
                # issue only on single column data frame
                inputs = self.__load_data(data=inputs[0],
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_INPUT)
            else:
                inputs, additional_data = self.data.iloc[index_raw_data]
                inputs = self.__load_data(data=inputs,
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_INPUT)
                additional_data = self.__load_data(data=additional_data,
                                                   augment=augment,
                                                   index=index,
                                                   entry_type=DEEP_ENTRY_ADDITIONAL_DATA)
        else:
            if not self.list_additional_data:
                inputs, labels = self.data.iloc[index_raw_data]
                inputs = self.__load_data(data=inputs,
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_INPUT)
                labels = self.__load_data(data=labels,
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_LABEL)
            else:
                inputs, labels, additional_data = self.data.iloc[index_raw_data]
                inputs = self.__load_data(data=inputs,
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_INPUT)
                labels = self.__load_data(data=labels,
                                          augment=augment,
                                          index=index,
                                          entry_type=DEEP_ENTRY_LABEL)
                additional_data = self.__load_data(data=additional_data,
                                                   augment=augment,
                                                   index=index,
                                                   entry_type=DEEP_ENTRY_ADDITIONAL_DATA)
        return inputs, labels, additional_data

    def __len__(self) -> int:
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Get the size of the dataset

        PARAMETERS:
        ----------

        None

        RETURN:
        -------

        return -> Integer : Length of the dataset
        """
        if self.number is None:
            return len(self.data)
        else:
            return self.number

    """
    "
    " PUBLIC METHODS
    "
    """

    def summary(self) -> None:
        """
        AUTHORS:
        --------
        author: Alix Leroy and Samuel Westlake

        DESCRIPTION:
        ------------
        Print the summary of the dataset

        PARAMETERS:
        -----------
        None

        RETURN:
        -------
        :return: None
        """
        for row in str(self.data.iloc[0:self.__len__()]).split("\n"):
            Notification(DEEP_NOTIF_INFO, row)

    def set_cv_library(self, cv_library ) -> None:
        """
         AUTHORS:
         --------

         :author: Samuel Westlake
         :author: Alix Leroy

         DESCRIPTION:
         ------------

         Set self.cv_library to the given value and import the corresponding cv library

         PARAMETERS:
         -----------

         :param cv_library(): The Flag of the computer vision library selected

         RETURN:
         -------

         None
         """
        self.cv_library = cv_library
        self.__import_cv_library()

    def load(self) -> None:
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Load the dataset into memory

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return: None
        """
        # Read the data given as input
        inputs = self.__read_data(self.inputs)
        labels = self.__read_data(self.labels)
        additional_data = self.__read_data(self.additional_data)

        # Create a dictionary containing inputs, labels and additional data
        if not labels:
            if not additional_data:
                d = {'inputs': inputs}
            else:
                d = {'inputs': inputs, '_additional_data': additional_data}
        else:
            if not additional_data:
                d = {'inputs': inputs, 'labels': labels}
            else:
                d = {'inputs': inputs, 'labels': labels, 'additional_data': additional_data}
        # Convert the dictionary of data into a panda DataFrame
        try:
            self.data = pd.DataFrame(d)
        except ValueError as e:
            error_entry_array_size(d, e)
        self.__set_number()
        Notification(DEEP_NOTIF_SUCCESS, DEEP_MSG_DATA_LOADED % self.name)

    def shuffle(self, method: int) -> None:
        """
        AUTHORS:
        --------
        author: Alix Leroy

        DESCRIPTION:
        ------------
        Shuffle the dataframe containing the data

        PARAMETERS:
        -----------
        None

        RETURN:
        -------
        :return: None
        """

        if method == DEEP_SHUFFLE_ALL:
            try:
                self.data = self.data.sample(frac=1).reset_index(drop=True)
            # TODO: Please can this except a specific error(s)
            except:
                Notification(DEEP_NOTIF_ERROR, "Cannot shuffle the dataset")
        else:
            Notification(DEEP_NOTIF_ERROR, "The shuffling method does not exist.")

        # Reset the TransformManager
        self.reset()

    def reset(self) -> None:
        """
        AUTHORS:
        --------
        :author: Alix Leroy

        DESCRIPTION:
        ------------
        Reset the transform_manager

        PARAMETERS:
        -----------
        None

        RETURN:
        -------
        :return: None
        """
        if self.transform_manager is not None:
            self.transform_manager.reset()

    """
    "
    " PRIVATE METHODS
    "
    """

    def __set_number(self) -> None:
        """
        AUTHORS:
        --------
        author: Samuel Westlake, Alix Leroy

        DESCRIPTION:
        ------------
        Set the length of the dataset

        RETURN:
        -------
        :return: None
        """
        if self.number is None:
            self.number = len(self.data)
            Notification(DEEP_NOTIF_INFO, DEEP_MSG_DATA_NO_LENGTH % len(self.data))
        else:
            if self.number > len(self.data):
                self.number = len(self.data)
                Notification(DEEP_NOTIF_WARNING, DEEP_MSG_DATA_TOO_LONG % len(self.data))
            else:
                Notification(DEEP_NOTIF_INFO, DEEP_MSG_DATA_LENGTH % (len(self.data), self.number))

    def __import_cv_library(self):
        """
        AUTHORS:
        --------
        author: Samuel Westlake

        DESCRIPTION:
        ------------
        Imports either cv2 or PIL.Image dependant on the value of self.cv_library

        PARAMETERS:
        -----------
        None

        RETURN:
        -------
        None
        """
        if self.cv_library == DEEP_LIB_OPENCV:
            try:
                Notification(DEEP_NOTIF_INFO, DEEP_MSG_CV_LIBRARY_SET % "OPENCV")
                global cv2
                import cv2
            except ImportError as e:
                Notification(DEEP_NOTIF_ERROR, str(e))
        elif self.cv_library == DEEP_LIB_PIL:
            try:
                Notification(DEEP_NOTIF_INFO, DEEP_MSG_CV_LIBRARY_SET % "PILLOW")
                global Image
                from PIL import Image
            except ImportError as e:
                Notification(DEEP_NOTIF_ERROR, str(e))
        else:
            Notification(DEEP_NOTIF_ERROR, DEEP_MSG_CV_LIBRARY_NOT_IMPLEMENTED % self.cv_library)

    def __read_data(self, list_f_data):
        """
        AUTHORS:
        --------

        author: Alix Leroy
        author:  Samuel Westlake

        DESCRIPTION:
        ------------

        Read the content given in the input files or folders

        PARAMETERS:
        -----------

        :param list_f_data : List of files or folders

        RETURN:
        -------

        :return final_data: The content of the files and folder given as input. The list is formatted to fit a pandas Dataframe columns
        """
        data = []


        # For all the entries given
        for i, e_data in enumerate(list_f_data):
            content = []

            # If the entry given is a list of entries to extend
            if type(e_data["path"]) is list:

                # For each entry in the list we collect the data and extend the list
                for j, entry in enumerate(e_data["path"]):
                    content.extend(self.__get_content(entry))
                data.append(content)

            # If the given entry is a single entry
            else:
                content = self.__get_content(e_data["path"])
                data.append(content)  # Add the new content to the list of data



        # Format the data to the format accepted by deeplodocus where final_data[i][j] = data[j][i]
        final_data = []
        if len(data) > 0:
            for i in range(len(data[0])):
                temp_data = []
                for j in range(len(data)):
                    try:
                        temp_data.append(data[j][i])
                    except IndexError as e:
                        # TODO : Have a more explicit notification
                        Notification(DEEP_NOTIF_FATAL, "All your entries do not have the same number of instances : " + str(e))
                final_data.append(temp_data)
        return final_data

    def __get_content(self, f):
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        List all the data from a file or from a folder

        PARAMETERS:
        -----------
        :param f: A file or a folder

        RETURN:
        -------

        :return content: Content of the file/folder in a list
        """
        # Get the source path type
        source_type = self.__source_path_type(f)
        content = None
        # If f is a file
        if source_type == DEEP_TYPE_FILE:
            with open(f) as f:  # Read the file and get the data
                content = f.readlines()
            content = [x.strip() for x in content]  # Remove the end of line \n
        # If f is a folder
        elif source_type == DEEP_TYPE_FOLDER:  # If it is a folder given as input
            content = self.__get_file_paths(f)
        # Else (neither a file nor a folder)
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_SOURCE_NOT_FOUND % f)
        return content

    def __get_file_paths(self, directory):
        """
        AUTHORS:
        --------

        author: Samuel Westlake
        author: Alix Leroy

        DESCRIPTION:
        ------------

        Get the list of paths to every file within the given directories

        PARAMETERS:
        -----------

        :param directory: str or list of str: path to directories to get paths from

        RETURN:
        -------

        :return list of str: list of paths to every file within the given directories

        """
        paths = []
        # For each item in the directory
        for item in os.listdir(directory):
            sub_path = "%s/%s" % (directory, item)
            # If the subpath of the item is a directory we apply the self function recursively
            if os.path.isdir(sub_path):
                paths.extend(self.__get_file_paths(sub_path))
            # Else we add the path of the file to the list of files
            else:
                paths.extend([sub_path])
        return sorted_nicely(paths)

    def __load_data(self, data, augment, index, entry_type, entry_num=None):
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Load (and transform is needed) the requested data

        PARAMETERS:
        -----------

        :param data: The path to the data which has to be loaded
        :param augment: Whether to augment or not the requested data
        :param index: The index of the data
        :param entry_type: Whether it in an input, a label or an additional_data
        :param entry_num: Number of the entry (input1, input2, ...) (useful for sequences)

        RETURN:
        -------

        :return loaded_data: The loaded (and transformed if required) data
        """
        loaded_data = []
        for i, d in enumerate(data):            # For each data given in the list (list = one instance of each file)
            if d is not None:
                type_data = self.__data_type(d)
                # TODO : Check how sequence behaves
                # If data is a sequence we use the function in a recursive fashion
                if type_data == DEEP_TYPE_SEQUENCE:
                    if entry_num is None:
                        entry_num = i
                    sequence_raw_data = d.split()  # Generate a list from the sequence
                    loaded_data.append(self.__load_data(data=sequence_raw_data,
                                                        augment=augment,
                                                        index=index,
                                                        entry_type=entry_type,
                                                        entry_num=entry_num))  # Get the content of the list
                # Image
                elif type_data == DEEP_TYPE_IMAGE:
                    image = self.__load_image(d)
                    if self.cv_library == DEEP_LIB_PIL:
                        image = np.array(image)
                    if entry_num is None:
                        entry_num = i
                    if augment is True:
                        image = self.transform_manager.transform(data=image,
                                                                 index=index,
                                                                 type_data=type_data,
                                                                 entry_type=entry_type,
                                                                 entry_num=entry_num)
                    image = np.swapaxes(image, 0, 2).astype(float)
                    loaded_data.append(image)
                # TODO : Check how video behaves
                # Video
                elif type_data == DEEP_TYPE_VIDEO:
                    video = self.__load_video(d)
                    if entry_num is None:
                        entry_num = i
                    if augment is True:
                        video = self.transform_manager.transform(data=video,
                                                                 index=index,
                                                                 type_data=type_data,
                                                                 entry_type=entry_type,
                                                                 entry_num=entry_num)
                    loaded_data.append(video)
                # Integer
                elif type_data == DEEP_TYPE_INTEGER:
                    integer = int(d)
                    loaded_data.append(integer)
                # Float
                elif type_data == DEEP_TYPE_FLOAT:
                    floating = float(d)
                    loaded_data.append(floating)
                # Numpy array
                elif type_data == DEEP_TYPE_NP_ARRAY:
                    loaded_data.append(np.load(d))
                # Data type not recognized
                else:
                    Notification(DEEP_NOTIF_FATAL,
                                 "The following data could not be loaded because its type is not recognize : %s.\n"
                                 "Please check the documentation online to see the supported types" % data)
                entry_num = None
            # If the data is None
            else:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_IS_NONE % d)
        return loaded_data

    """
    "
    " DATA TYPE ANALYZERS
    "
    """

    @staticmethod
    def __source_path_type(f):
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Find the type of the source path

        PARAMETERS:
        -----------

        A source path

        RETURN:
        -------

        :return type -> int: A type flag
        """
        # If the source path is a file
        if os.path.isfile(f):
            return DEEP_TYPE_FILE
        # If the source path is a directory
        elif os.path.isdir(f):
            return DEEP_TYPE_FOLDER
        # TODO: Add database as source path
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_SOURCE_NOT_FOUND % f)
            return None

    @staticmethod
    def __data_type(data) -> int:
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Find the type of the given data

        PARAMETERS:
        -----------

        :param data: The data to analyze

        RETURN:
        -------

        :return: The integer flag of the corresponding type
        """
        mime = mimetypes.guess_type(data)
        if mime[0] != None:
            mime = mime[0].split("/")[0]

        # Image
        if mime == "image":
            return DEEP_TYPE_IMAGE
        # Video
        elif mime == "video":
            return DEEP_TYPE_VIDEO
        # Float
        elif get_int_or_float(data) == DEEP_TYPE_FLOAT:
            return DEEP_TYPE_FLOAT
        # Integer
        elif get_int_or_float(data) == DEEP_TYPE_INTEGER:
            return DEEP_TYPE_INTEGER
        # List
        elif type(data) is list:
            return DEEP_TYPE_SEQUENCE
        if is_np_array(data) is True:
            return DEEP_TYPE_NP_ARRAY
        # Type not handled
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_NOT_HANDLED % data)

    #
    # DATA LOADERS
    #
    def __load_image(self, image_path: str):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Load the image in the image_path

        PARAMETERS:
        -----------

        :param image_path->str: The path of the image to load

        RETURN:
        -------

        :return: The loaded image
        """
        if self.cv_library == DEEP_LIB_OPENCV:
            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            # Check that the image was correctly loaded
            if image is None:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_LOAD_IMAGE % image_path)
            # If the image is not grayscale
            if len(image.shape) > 2:
                # Convert to RGB(a)
                return self.__convert_bgra2rgba(image)
            else:
                return image[:, :, np.newaxis]
        elif self.cv_library == DEEP_LIB_PIL:
            try:
                return Image.open(image_path)
            except FileNotFoundError:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_FIND_IMAGE % image_path)
            except OSError:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_IDENTIFY_IMAGE % ("PIL", image_path))
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_CV_LIBRARY_NOT_IMPLEMENTED % self.cv_library)

    @staticmethod
    def __convert_bgra2rgba(image):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Convert BGR(alpha) image to RGB(alpha) image

        PARAMETERS:
        -----------

        :param image: image to convert

        RETURN:
        -------

        :return: a RGB(alpha) image
        """

        # Convert BGR(A) to RGB(A)
        _, _, channels = image.shape
        # Handle BGR and BGRA images
        if channels == 3:
            image = image[:, :, (2, 1, 0)]
        elif channels == 4:
            image = image[:, :, (2, 1, 0, 3)]
        return image

    def __load_video(self, video_path: str):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------
        Load a video

        PARAMETERS:
        -----------

        :param video_path->str: absolute path to a video

        RETURN:
        -------

        :return: a list of frame from the video
        """
        self.__throw_warning_video()
        video = []
        # If the computer vision library selected is OpenCV
        if self.cv_library == DEEP_LIB_OPENCV:
            # try to load the file
            cap = cv2.VideoCapture(video_path)
            while True:
                _, frame = cap.read()
                if frame is None:
                    break
                video.append(self.__convert_bgra2rgba(frame))
            cap.release()
        return video

    def __throw_warning_video(self):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Warn the user of the unsupported vidoe mode.

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return: None
        """
        if self.warning_video is None:
            Notification(DEEP_NOTIF_WARNING, "The video mode is not fully supported. We deeply suggest you to use sequences of images.")
            self.warning_video = 1

    """
    "
    " CHECKERS
    "
    """

    def __temp_convert_str2dict(self, entries):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Temporary change strings to dict for loading entry

        PARAMETERS:
        -----------

        :param entries:

        RETURN:
        -------

        :return: None
        """
        for i, entry in enumerate(entries):
            entries[i] = ast.literal_eval(entry)
        return entries

    @staticmethod
    def __check_null_entry(entry):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Check if an entry is Null

        PARAMETERS:
        -----------

        :param entry: The entry to check

        RETURN:
        -------

        :return ->list: The formatted entry
        """

        try:
            if entry is None:
                return []
            elif entry[0] is None:
                return []
            else:
                return entry
        except IndexError:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_ENTRY % entry)

    def __check_load_method(self, load_method):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Check if the load method required is valid.
        Check if the load method given is an integer, otherwise convert it to the corresponding flag

        PARAMETERS:
        -----------

        :param load_method:

        RETURN:
        -------

        :return load_method (int): The corresponding DEEP_LOAD_METHOD flag
        """

        if isinstance(load_method, int):
            if load_method in DEEP_LOAD_METHOD_LIST:
                return load_method
            else:
                Notification(DEEP_NOTIF_FATAL, "The given flag '%i' does not correspond to any DEEP_LOAD_METHOD" %load_method)
        else:
            if load_method == "default":
                return DEEP_LOAD_METHOD_MEMORY
            elif load_method =="memory":
                return DEEP_LOAD_METHOD_MEMORY
            elif load_method in ["harddrive", "hard drive", "hard-drive", "hard_drive"]:
                Notification(DEEP_NOTIF_FATAL, "Loading data using a hard drive reading is not currently implemented")
                return DEEP_LOAD_METHOD_HARDDRIVE
            elif load_method == "server":
                Notification(DEEP_NOTIF_FATAL, "Loading data using a server is not currently implemented")
                return DEEP_LOAD_METHOD_SERVER
            else:
                Notification(DEEP_NOTIF_FATAL, "The following loading method does not exist : %s" %str(load_method))

    def __check_data(self):
        """
        Author : Alix Leroy
        Check the validity of the data given as inputs
        :return:
        """
        Notification(DEEP_NOTIF_INFO, "Checking the data ...")
        # Check the number of data
        self.__check_data_num_instances()
        # Check the type of the data
        # TODO : Add a progress bar
        # Check data is available
        # TODO : Add a progress bar
        Notification(DEEP_NOTIF_SUCCESS, "Data checked without any error.")

    def __check_data_num_instances(self):
        """
        :return:
        """
        # TODO : Add a progress bar
        # For each file check if we have the same number of row
        for f_data in self.data:
            num_instances = 0
            # If the input given is a list of inputs
            if type(f_data) is list:
                # For each input in the list we collect the data and extend the list
                for j, f in enumerate(f_data):
                    num_instances += self.__compute_number_instances(f)
            # If the input given is a single input
            else:
                num_instances = self.__compute_number_instances(f_data)
            if num_instances != self.number_instances:
                Notification(DEEP_NOTIF_FATAL, "Number of instances in " + str(self.inputs[0]) + " and " + str(f) + " do not match.")

    def __check_data_type(self):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Check the type of the entries

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return: None
        """

        # TODO : Add a progress bar
        # For each file check if we have the same number of row
        for f in self.list_data:
            # If the input is a file
            if self.__source_path_type(f) == DEEP_TYPE_FILE:
                with open(f) as file:
                    Notification(DEEP_NOTIF_ERROR, "Check data type not implemented")
            # If the input is a folder
            elif self.__source_path_type(f) == DEEP_TYPE_FOLDER:
                Notification(DEEP_NOTIF_FATAL, "Cannot currently check folders")
            # If it is not a file neither a folder then BUG :(
            else:
                Notification(DEEP_NOTIF_FATAL, "The following path is neither a file nor a folder : " + str(f) + ".")
    #
    # DATA UTILS
    #

    def __compute_number_raw_instances(self):
        """
        Author: Alix Leroy
        Compute the theoretical number of instances in each epoch
        The first given file/folder stands as the frame to count
        :return: theoretical number of instances in each epoch
        """
        num_instances = 0
        # If the input given is a list of inputs
        if type(self.inputs[0]["path"]) is list:

            # For each input in the list we collect the data and extend the list
            for j, f in enumerate(self.inputs[0]["path"]):
                num_instances += self.__get_number_instances(f)
        # If the input given is a single input
        else:
            num_instances = self.__get_number_instances(self.inputs[0]["path"])
        return num_instances

    """
    "
    " SETTERS
    "
    """

    def set_use_raw_data(self, use_raw_data: bool) -> None:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Set the use_raw_data attribut to new value

        PARAMETERS:
        -----------

        :param use_raw_data: Bool : Whether to use or not the raw data in the training


        RETURN:
        -------

        return: None
        """
        self.use_raw_data = use_raw_data

    """
    "
    " GETTERS
    "
    """

    def __get_number_instances(self, f):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Get the number of instances in a file or a folder

        PARAMETERS:
        ------------

        :param e: an entry

        RETURN:
        -------

        :return num_instances(int): Number of instances in the file or the folder
        """
        # If the frame input is a file
        if self.__source_path_type(f) == DEEP_TYPE_FILE:
            with open(f) as f:
                num_instances = sum(1 for _ in f)
        # If the frame input is a folder
        elif self.__source_path_type(f) == DEEP_TYPE_FOLDER:
            raise ValueError("Not implemented")
        # If it is not a file neither a folder then BUG :(
        else:
            Notification(DEEP_NOTIF_FATAL, "The following input is neither a file nor a folder :" + str(f))
        return num_instances


# Python import
from typing import List
from typing import Union
from typing import Any

# Deeplodocus imports
from deeplodocus.data.entry import Entry
from deeplodocus.utils.generic_utils import get_corresponding_flag

# Deeplodocus flags
from deeplodocus.utils.flags.source import *
from deeplodocus.utils.flags.flag_lists import *


class Dataset(object):
    """
    AUTHORS:
    --------

    :author : Alix Leroy
    :author: Samuel Westlake


    DESCRIPTION:
    ------------

    A Dataset class to manage the data given by the config files.
    The following class permits :
        - Data checking
        - Smart data loading
        - Data formatting
        - Data transform (through the TransformManager class)


    The dataset is splitted into 3 subsets :
        - Inputs : Data given as input to the network
        - Labels : Data given as output (ground truth) to the network (optional)
        - Additional data : Data given to the loss function (optional)

    The dataset class supports 2 different image processing libraries :
        - PILLOW (fork of PIL) as default
        - OpenCV (usage recommended for efficiency)
    """

    def __init__(self,
                 inputs=None,
                 labels=None,
                 additional_data=None,
                 number=None,
                 name="Default",
                 use_raw_data=True,
                 cv_library: Flag = DEEP_LIB_PIL,
                 transform_manager=None):
        """
        AUTHORS:
        --------

        author: Alix Leroy
        author:

        DESCRIPTION:
        ---------

        Initialize the dataset

        PARAMETERS:
        -----------

        :param inputs: A list of input files/folders/list of files/folders
        :param labels: A list of label files/folders/list of files/folders
        :param additional_data: A list of additional data files/folders/list of files/folders
        :param use_raw_data: Boolean : Whether to feed the network with raw data or always apply transforms on it
        :param transform_manager: A TransformManager instance
        :param name: Name of the dataset

        RETURN:
        -------

        :return: None
        """
        self.list_inputs = self.__generate_entries(entries=self.__check_null_entry(inputs), entry_type=DEEP_ENTRY_INPUT)
        self.list_labels = self.__generate_entries(entries=self.__check_null_entry(labels), entry_type=DEEP_ENTRY_LABEL)
        self.list_additional_data = self.__generate_entries(entries=self.__check_null_entry(additional_data), entry_type=DEEP_ENTRY_ADDITIONAL_DATA)
        self.number_raw_instances = self.__calculate_number_raw_instances()
        self.length = self.__compute_length(desired_length=number, num_raw_instances=self.number_raw_instances)
        self.name = name
        self.transform_manager = transform_manager
        self.use_raw_data = use_raw_data
        self.warning_video = None
        self.cv_library = None
        self.set_cv_library(cv_library)
        self.item_order = np.arange(self.length)

    def __getitem__(self, index: int):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Get the selected item
        The item is selected accordingly to the required function

        PARAMETERS:
        -----------

        :param item:

        RETURN:
        -------

        :return instance: Loaded and possibly transformed instance to be given to the training
        """

        # If the index given is too big => Error
        if index >= self.length:
            Notification(DEEP_NOTIF_FATAL, "The given instance index is too high : " + str(index))
        # Else we get the random generated index
        else:
            index = self.item_order[index]

        inputs = []
        labels = []
        additional_data = []

        # If we ask for a not existing index we use the modulo and consider the data to have to be augmented
        if index >= self.number_raw_instances:
            augment = True
        # If we ask for a raw data, augment it only if required by the user
        else:
            augment = not self.use_raw_data

        # Extract lists of raw data for the selected index
        if not self.list_labels:
            if not self.list_additional_data:
                inputs = self.__load(entries=self.list_inputs,
                                     index=index,
                                     augment=augment)

            else:
                inputs = self.__load(entries=self.list_inputs,
                                     index=index,
                                     augment=augment)
                additional_data = self.__load(entries=self.list_additional_data,
                                              index=index,
                                              augment=augment)
        else:
            if not self.list_additional_data:
                inputs = self.__load(entries=self.list_inputs,
                                     index=index,
                                     augment=augment)
                labels = self.__load(entries=self.list_labels,
                                     index=index,
                                     augment=augment)
            else:
                inputs = self.__load(entries=self.list_inputs,
                                     index=index,
                                     augment=augment)
                labels = self.__load(entries=self.list_labels,
                                     index=index,
                                     augment=augment)
                additional_data = self.__load(entries=self.list_additional_data,
                                              index=index,
                                              augment=augment)

        return inputs, labels, additional_data

    """
    "
    " LENGTH
    "
    """
    def __len__(self) -> int:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Get the length of the data set

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return (int): The length of the data set
        """

        return self.length

    @staticmethod
    def __compute_length(desired_length : int, num_raw_instances : int) -> int:
        """
        AUTHORS:
        --------

        :author: Alix Leroy
        :author: Samuel Westlake

        DESCRIPTION:
        ------------

        Calculate the length of the dataset

        PARAMETERS:
        -----------

        :param desired_length(int): The desired number of instances
        :param num_raw_instances(int): The actual number of instance in the sources

        RETURN:
        -------

        :return (int): The length of the dataset
        """

        if desired_length is None:
            Notification(DEEP_NOTIF_INFO, DEEP_MSG_DATA_NO_LENGTH % num_raw_instances)
            return num_raw_instances
        else:
            if desired_length > num_raw_instances:
                Notification(DEEP_NOTIF_INFO, DEEP_MSG_DATA_GREATER % (desired_length, num_raw_instances))
                return desired_length
            elif desired_length < num_raw_instances:
                Notification(DEEP_NOTIF_WARNING, DEEP_MSG_DATA_SHORTER % (num_raw_instances, desired_length))
                return desired_length
            else:
                Notification(DEEP_NOTIF_INFO, DEEP_MSG_DATA_LENGTH % num_raw_instances)
                return desired_length

    def __calculate_number_raw_instances(self) -> int:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Calculate the theoretical number of instances in each epoch
        The first given file/folder stands as the frame to count

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return num_raw_instances (int): theoretical number of instances in each epoch
        """
        # Calculate for the first entry
        num_raw_instances = self.list_inputs[0].__len__()

        # Gather all the entries in one list
        entries = self.list_inputs + self.list_labels + self.list_additional_data

        # For each entry check if the number of raw instances is the same as the first input
        for index, entry in enumerate(entries):
            n = entry.__len__()

            if n != num_raw_instances:
                Notification(DEEP_NOTIF_FATAL, "Number of instances in " + str(self.list_inputs[0].get_entry_type()) +
                             "-" + str(self.list_inputs[0].get_entry_index()) + " and " + str(entry.get_entry_type()) +
                             "-" + str(entry.get_entry_index())+ " do not match.")
        return num_raw_instances

    def __load(self, entries : List[Entry], index : int, augment: bool) -> List[Any]:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Load one instance of the dataset into memory

        PARAMETERS:
        -----------

        :param entries(List[Entry]): The list of entries to load the instance from
        :param index(int): The index of the instance
        :param augment(bool): Whether to augment the data or not

        RETURN:
        -------

        :return data(List[Any]): The loaded and transformed data
        """
        data = []

        # Get the index of the original instance (before transformation)
        index_raw_instance = index % self.number_raw_instances

        # Gather the item of each entry
        for entry in entries:
            entry_data, is_loaded, is_transformed = entry.__getitem__(index=index_raw_instance)

            # LOAD THE ITEM
            if is_loaded is False:
                entry_data = self.__load_data_from_str(data=entry_data,
                                                       entry=entry)

            # TRANSFORM THE ITEM
            if is_transformed is False and augment is True:
                entry_data = self.__transform_data(data=entry_data,
                                                   entry=entry,
                                                   index=index)
            data.append(entry_data)
        return data

    def __generate_entries(self, entries: List[Namespace], entry_type : Flag) -> List[Entry]:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Generate a list of Entry instances

        PARAMETERS:
        -----------

        :param entries (List[Namespace]): The list of raw entries in a Namespace format
        :param entry_type (Flag): The flag of the entry type

        RETURN:
        -------

        :return generated_entries (List(Entry)): The list of Entry instances generated
        """
        # List of generated entries to an Entry class format
        generated_entries = []

        # For each entry in a Namespace format
        for index, entry in enumerate(entries):

            # Check the completeness of the entry
            entry = self.__check_entry_completeness(entry)
            # Create the Entry instance
            new_entry = Entry(sources=entry.source,
                              join=entry.join,
                              data_type=entry.type,
                              load_method=entry.load_method,
                              entry_index=index,
                              entry_type=entry_type)
            generated_entries.append(new_entry)

        return generated_entries

    @staticmethod
    def __check_entry_completeness(entry: Namespace) -> Namespace:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Check if the dictionary formatted entry is complete.
        If not complete, fill the dictionary with default value

        PARAMETERS:
        -----------

        :param entry (Namespace): The entry to check the completeness

        RETURN:
        -------

        :return entry (Namespace): The completed entry

        RAISE:
        ------

        :raise DeepError: Raised if the path is not given
        """

        # SOURCE
        if entry.check("source", None) is False:
            Notification(DEEP_NOTIF_FATAL, "The source was not specified to the following entry : %s" % str(entry.get()))

        # JOIN PATH
        if entry.check("join", None) is False:
            entry.add({"join" : None}, None)

        # LOADING METHOD
        if entry.check("load_method", None) is False:
            entry.add({"load_method" : "online"})

        # DATA TYPE
        if entry.check("type", None) is False:
            entry.add({"type" : None})

        return entry

    def __load_data_from_str(self, data: Union[str, List[str], Any], entry: Entry) -> Union[Any, List[Any]]:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Load a data from a string format to the actual content
        Loads either one item or a list of items

        PARAMETERS:
        -----------

        :param data(Union[str, List[str]]): The data to transform
        :param entry (Entry): The entry to which the item is attached

        RETURN:
        -------

        :return loaded_data(Union[Any, List[Any]]): The loaded data
        """

        loaded_data = None

        # Get data type index (only use the index for efficiency in the loop)
        dtype_flag_index = entry.get_data_type()()

        # Make sure the data contains something
        if data is not None:

            # If data is a sequence we use the function in a recursive fashion
            # SEQUENCE
            if dtype_flag_index == DEEP_DTYPE_SEQUENCE():
                # Get the content of the list
                sequence_raw_data = data.split()  # Generate a list from the sequence
                loaded_data = []
                for d in sequence_raw_data:
                    ld = self.__load_data_from_str(data=d,
                                                   entry=entry)
                    loaded_data.append(ld)

            # IMAGE
            elif dtype_flag_index == DEEP_DTYPE_IMAGE():
                # Load image
                loaded_data = self.__load_image(data)

                # Swap axes for PyTorch
                loaded_data = np.swapaxes(loaded_data, 0, 2).astype(float)

            # VIDEO
            elif dtype_flag_index == DEEP_DTYPE_VIDEO():
                loaded_data = self.__load_video(data)

            # INTEGER
            elif dtype_flag_index == DEEP_DTYPE_INTEGER():
                loaded_data = int(data)

            # FLOAT NUMBER
            elif dtype_flag_index == DEEP_DTYPE_FLOAT():
                loaded_data = float(data)

            # NUMPY ARRAY
            elif dtype_flag_index == DEEP_DTYPE_NP_ARRAY():
                loaded_data = np.load(data)

            # Data type not recognized
            else:
                Notification(DEEP_NOTIF_FATAL,
                             "The following data could not be loaded because its type is not recognize : %s.\n"
                             "Please check the documentation online to see the supported types" % data)
        # If the data is None
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_IS_NONE % data)

        return loaded_data

    def __transform_data(self, data: Union[Any, List[Any]], index: int, entry: Entry) -> Union[Any, List[Any]]:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Transform the data
        Transform either one item or a list of item

        PARAMETERS:
        -----------

        :param data(Union[Any, List[Any]]): The data to transform
        :param index (int): The index of the instance
        :param entry (Entry): The entry to which the item is attached

        RETURN:
        -------

        :return transformed_data(Union[Any, List[Any]]): The transformed data
        """

        # If we want to transform a sequence we use the function recursively
        if isinstance(data, list):
            transformed_data = []

            for d in data:
                td = self.__transform_data(data=d,
                                           index=index,
                                           entry=entry)
                transformed_data.append(td)

        # If it is only one item to transform
        else:
            transformed_data = self.transform_manager.transform(data=data,
                                                                index=index,
                                                                entry=entry)

        return transformed_data


    """
    "
    " DATA LOADERS
    "
    """

    def __load_image(self, image_path: str):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Load the image in the image_path

        PARAMETERS:
        -----------

        :param image_path(str): The path of the image to load

        RETURN:
        -------

        :return: The loaded image
        """
        # LOAD USING OPENCV
        if self.cv_library() == DEEP_LIB_OPENCV():
            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            # Check that the image was correctly loaded
            if image is None:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_LOAD_IMAGE % ("OpenCV", image_path))
            # If the image is not grayscale
            if image.ndim > 2:
                # Convert to BGR(a) to RGB(a)
                return self.__convert_bgra2rgba(image)
            else:
                image = image[:, :, np.newaxis]
                return image

        # LOAD USING PIL
        elif self.cv_library() == DEEP_LIB_PIL():
            try:
                return np.array(Image.open(image_path))
            except FileNotFoundError:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_FIND_IMAGE % ("PIL", image_path))
            except OSError:
                Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_CANNOT_IDENTIFY_IMAGE % ("PIL", image_path))
        else:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_CV_LIBRARY_NOT_IMPLEMENTED % self.cv_library)

    @staticmethod
    def __convert_bgra2rgba(image):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Convert BGR(alpha) image to RGB(alpha) image

        PARAMETERS:
        -----------

        :param image: image to convert

        RETURN:
        -------

        :return: a RGB(alpha) image
        """

        # Get the number of channels in the image
        _, _, channels = image.shape

        # Handle BGR and BGR(A) images
        if channels == 3:
            image = image[:, :, (2, 1, 0)]
        elif channels == 4:
            image = image[:, :, (2, 1, 0, 3)]
        return image

    def __load_video(self, video_path: str):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------
        Load a video

        PARAMETERS:
        -----------

        :param video_path->str: absolute path to a video

        RETURN:
        -------

        :return: a list of frame from the video
        """
        self.__throw_warning_video()
        video = []
        # If the computer vision library selected is OpenCV
        if self.cv_library() == DEEP_LIB_OPENCV():
            # try to load the file
            cap = cv2.VideoCapture(video_path)
            while True:
                _, frame = cap.read()
                if frame is None:
                    break
                video.append(self.__convert_bgra2rgba(frame))
            cap.release()
        else:
            Notification(DEEP_NOTIF_FATAL, "The video could not be loaded because OpenCV is not selected as the Computer Vision library")
        return video

    def __throw_warning_video(self):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Warn the user of the unstable video mode.

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        :return: None
        """
        if self.warning_video is None:
            Notification(DEEP_NOTIF_WARNING, "The video mode is not fully supported. "
                                             "We deeply suggest you to use sequences of images.")
            self.warning_video = 1

    def set_cv_library(self, cv_library : Flag) -> None:
        """
         AUTHORS:
         --------

         :author: Samuel Westlake
         :author: Alix Leroy

         DESCRIPTION:
         ------------

         Set self.cv_library to the given value and import the corresponding cv library

         PARAMETERS:
         -----------

         :param cv_library(Flag): The flag of the computer vision library selected

         RETURN:
         -------

         None
         """
        self.cv_library = get_corresponding_flag(flag_list=DEEP_LIST_CV_LIB, info=cv_library)
        self.__import_cv_library(cv_library=cv_library)

    @staticmethod
    def __import_cv_library(cv_library : Flag) -> None:
        """
        AUTHORS:
        --------

        :author: Samuel Westlake
        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Imports either cv2 or PIL.Image dependant on the value of cv_library

        PARAMETERS:
        -----------

        None

        RETURN:
        -------

        None
        """
        if DEEP_LIB_OPENCV.corresponds(info=cv_library):
            try:
                #Notification(DEEP_NOTIF_INFO, DEEP_MSG_CV_LIBRARY_SET % "OPENCV")
                global cv2
                import cv2
            except ImportError as e:
                Notification(DEEP_NOTIF_ERROR, str(e))
        elif DEEP_LIB_PIL.corresponds(info=cv_library):
            try:
                #Notification(DEEP_NOTIF_INFO, DEEP_MSG_CV_LIBRARY_SET % "PILLOW")
                global Image
                from PIL import Image
            except ImportError as e:
                Notification(DEEP_NOTIF_ERROR, str(e))
        else:
            Notification(DEEP_NOTIF_ERROR, DEEP_MSG_CV_LIBRARY_NOT_IMPLEMENTED % cv_library)

    @staticmethod
    def __check_null_entry(entry):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Check if an entry is Null

        PARAMETERS:
        -----------

        :param entry: The entry to check

        RETURN:
        -------

        :return ->list: The formatted entry
        """

        try:
            if entry is None:
                return []
            elif entry[0] is None:
                return []
            else:
                return entry
        except IndexError:
            Notification(DEEP_NOTIF_FATAL, DEEP_MSG_DATA_ENTRY % entry)

    def shuffle(self, method: Flag) -> None:
        """
        AUTHORS:
        --------

        author: Alix Leroy

        DESCRIPTION:
        ------------

        Shuffle the dataframe containing the data

        PARAMETERS:
        -----------

        :param method (Flag): The shuffling method Flag

        RETURN:
        -------

        :return: None
        """

        # ALL DATASET
        if DEEP_SHUFFLE_ALL.corresponds(info=method):
            self.item_order = np.random.randint(0, high=self.length, size=(self.length,))
            Notification(DEEP_NOTIF_SUCCESS, "Dataset shuffled")

        # NONE
        elif DEEP_SHUFFLE_NONE.corresponds(info=method):
            pass

        # BATCHES
        elif DEEP_SHUFFLE_BATCHES.corresponds(info=method):
            Notification(DEEP_NOTIF_ERROR, "Batch shuffling not implemented yet.")

        # WRONG FLAG
        else:
            Notification(DEEP_NOTIF_ERROR, "The shuffling method does not exist.")

        # Reset the TransformManager
        self.reset()

    def reset(self) -> None:
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------
        Reset the transform_manager

        PARAMETERS:
        -----------
        None

        RETURN:
        -------
        :return: None
        """
        if self.transform_manager is not None:
            self.transform_manager.reset()
