import random

from deeplodocus.data.transformer.transformer import Transformer


class OneOf(Transformer):
    """
    AUTHORS:
    --------

    :author: Alix Leroy

    DESCRIPTION:
    ------------

    OneOf class inheriting from Transformer which compute one random transform from the list
    """
    def __init__(self, name, mandatory_transforms, transforms):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Initialize a OneOf transformer inheriting a Transformer

        PARAMETERS:
        -----------

        :param config->Namespace: The config

        RETURN:
        -------

        :return: None
        """
        Transformer.__init__(self, name, mandatory_transforms, transforms)

    def transform(self, transformed_data, index):
        """
        AUTHORS:
        --------

        :author: Alix Leroy

        DESCRIPTION:
        ------------

        Transform the data using the One Of transformer

        PARAMETERS:
        -----------

        :param data: The data to transform
        :param index: The index of the data

        RETURN:
        -------

        :return transformed_data: The transformed data
        """
        transforms = []
        if self.__last_index == index:
            transforms += self.__last_transforms

        else: # Get ALL the mandatory transforms + one transform randomly selected
            transforms += self.__list_mandatory_transforms                                    # Get the mandatory transforms
            random_transform_index = random.randint(0, len(self.__list_transforms) -1)        # Get a random transform among the ones available in the list
            transforms += self.__list_transforms[random_transform_index]                      # Get the one function

        # Reinitialize the last transforms
        self.__last_transforms = []

        # Apply the transforms
        transformed_data = self.__apply_transforms(transformed_data, transforms)

        self.__last_index = index
        return transformed_data
