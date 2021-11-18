import copy
import datetime
import json
import logging
import types
from typing import Any, Callable, Optional, Set, Union

import great_expectations.exceptions as ge_exceptions
from great_expectations.core.id_dict import BatchKwargs, BatchSpec, IDDict
from great_expectations.core.util import convert_to_json_serializable
from great_expectations.exceptions import InvalidBatchIdError
from great_expectations.types import SerializableDictDot
from great_expectations.util import filter_properties_dict
from great_expectations.validator.metric_configuration import MetricConfiguration

logger = logging.getLogger(__name__)


BATCH_REQUEST_REQUIRED_TOP_LEVEL_KEYS: Set[str] = {
    "datasource_name",
    "data_connector_name",
    "data_asset_name",
}
BATCH_REQUEST_OPTIONAL_TOP_LEVEL_KEYS: Set[str] = {
    "data_connector_query",
    "runtime_parameters",
    "batch_identifiers",
    "batch_spec_passthrough",
}
DATA_CONNECTOR_QUERY_KEYS: Set[str] = {
    "batch_filter_parameters",
    "limit",
    "index",
    "custom_filter_function",
}
RUNTIME_PARAMETERS_KEYS: Set[str] = {
    "batch_data",
    "query",
    "path",
}
BATCH_SPEC_PASSTHROUGH_KEYS: Set[str] = {
    "sampling_method",
    "sampling_kwargs",
    "splitter_method",
    "splitter_kwargs",
    "reader_method",
    "reader_options",
}
BATCH_REQUEST_FLATTENED_KEYS: Set[str] = set().union(
    *[
        BATCH_REQUEST_REQUIRED_TOP_LEVEL_KEYS,
        BATCH_REQUEST_OPTIONAL_TOP_LEVEL_KEYS,
        DATA_CONNECTOR_QUERY_KEYS,
        RUNTIME_PARAMETERS_KEYS,
        BATCH_SPEC_PASSTHROUGH_KEYS,
    ]
)


class BatchDefinition(SerializableDictDot):
    def __init__(
        self,
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        batch_identifiers: IDDict,
        batch_spec_passthrough: Optional[dict] = None,
    ):
        self._validate_batch_definition(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            batch_identifiers=batch_identifiers,
        )

        assert type(batch_identifiers) == IDDict

        self._datasource_name = datasource_name
        self._data_connector_name = data_connector_name
        self._data_asset_name = data_asset_name
        self._batch_identifiers = batch_identifiers
        self._batch_spec_passthrough = batch_spec_passthrough

    def to_json_dict(self) -> dict:
        return convert_to_json_serializable(
            {
                "datasource_name": self.datasource_name,
                "data_connector_name": self.data_connector_name,
                "data_asset_name": self.data_asset_name,
                "batch_identifiers": self.batch_identifiers,
            }
        )

    def __repr__(self) -> str:
        doc_fields_dict: dict = {
            "datasource_name": self._datasource_name,
            "data_connector_name": self._data_connector_name,
            "data_asset_name": self.data_asset_name,
            "batch_identifiers": self._batch_identifiers,
        }
        return str(doc_fields_dict)

    @staticmethod
    def _validate_batch_definition(
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        batch_identifiers: IDDict,
    ):
        if datasource_name is None:
            raise ValueError("A valid datasource must be specified.")
        if datasource_name and not isinstance(datasource_name, str):
            raise TypeError(
                f"""The type of an datasource name must be a string (Python "str").  The type given is
"{str(type(datasource_name))}", which is illegal.
            """
            )
        if data_connector_name is None:
            raise ValueError("A valid data_connector must be specified.")
        if data_connector_name and not isinstance(data_connector_name, str):
            raise TypeError(
                f"""The type of a data_connector name must be a string (Python "str").  The type given is
"{str(type(data_connector_name))}", which is illegal.
                """
            )
        if data_asset_name is None:
            raise ValueError("A valid data_asset_name must be specified.")
        if data_asset_name and not isinstance(data_asset_name, str):
            raise TypeError(
                f"""The type of a data_asset name must be a string (Python "str").  The type given is
"{str(type(data_asset_name))}", which is illegal.
                """
            )
        if batch_identifiers and not isinstance(batch_identifiers, IDDict):
            raise TypeError(
                f"""The type of batch_identifiers must be an IDDict object.  The type given is \
"{str(type(batch_identifiers))}", which is illegal.
"""
            )

    #         if limit and not isinstance(limit, int):
    #             raise ge_exceptions.BatchDefinitionError(
    #                 f'''The type of limit must be an integer (Python "int").  The type given is "{str(type(limit))}", which
    # is illegal.
    #                 '''
    #             )

    @property
    def datasource_name(self) -> str:
        return self._datasource_name

    @property
    def data_connector_name(self) -> str:
        return self._data_connector_name

    @property
    def data_asset_name(self) -> str:
        return self._data_asset_name

    @property
    def batch_identifiers(self) -> IDDict:
        return self._batch_identifiers

    @property
    def batch_spec_passthrough(self) -> dict:
        return self._batch_spec_passthrough

    @batch_spec_passthrough.setter
    def batch_spec_passthrough(self, batch_spec_passthrough: Optional[dict]):
        self._batch_spec_passthrough = batch_spec_passthrough

    @property
    def id(self) -> str:
        return IDDict(self.to_json_dict()).to_id()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            # Delegate comparison to the other instance's __eq__.
            return NotImplemented
        return self.id == other.id

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2)

    def __hash__(self) -> int:
        """Overrides the default implementation"""
        _result_hash: int = hash(self.id)
        return _result_hash


class BatchRequestBase(SerializableDictDot):
    """
    This class is for internal inter-object protocol purposes only.
    As such, it contains all attributes of a batch_request, but does not validate them.
    See the BatchRequest class, which extends BatchRequestBase and validates the attributes.

    BatchRequestBase is used for the internal protocol purposes exclusively, not part of API for the developer users.

    Previously, the very same BatchRequest was used for both the internal protocol purposes and as part of the API
    exposed to developers.  However, while convenient for internal data interchange, using the same BatchRequest class
    as arguments to the externally-exported DataContext.get_batch(), DataContext.get_batch_list(), and
    DataContext.get_validator() API calls for obtaining batches and/or validators was insufficiently expressive to
    fulfill the needs of both. In the user-accessible API, BatchRequest, must enforce that all members of the triple,
    consisting of data_source_name, data_connector_name, and data_asset_name, are not NULL.  Whereas for the internal
    protocol, BatchRequest is used as a flexible bag of attributes, in which any fields are allowed to be NULL.  Hence,
    now, BatchRequestBase is dedicated for the use as the bag oof attributes for the internal protocol use, whereby NULL
    values are allowed as per the internal needs.  The BatchRequest class extends BatchRequestBase and adds to it strong
    validation (described above plus additional attribute validation) so as to formally validate user specified fields.
    """

    def __init__(
        self,
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        data_connector_query: Optional[dict] = None,
        limit: Optional[int] = None,
        runtime_parameters: Optional[dict] = None,
        batch_identifiers: Optional[dict] = None,
        batch_spec_passthrough: Optional[dict] = None,
    ):
        self._datasource_name = datasource_name
        self._data_connector_name = data_connector_name
        self._data_asset_name = data_asset_name
        self._data_connector_query = data_connector_query
        self._limit = limit

        self._runtime_parameters = runtime_parameters
        self._batch_identifiers = batch_identifiers
        self._batch_spec_passthrough = batch_spec_passthrough

    @property
    def runtime_parameters(self) -> dict:
        return self._runtime_parameters

    @property
    def batch_identifiers(self) -> dict:
        return self._batch_identifiers

    @property
    def datasource_name(self) -> str:
        return self._datasource_name

    @property
    def data_connector_name(self) -> str:
        return self._data_connector_name

    @property
    def data_asset_name(self) -> str:
        return self._data_asset_name

    @data_asset_name.setter
    def data_asset_name(self, data_asset_name):
        self._data_asset_name = data_asset_name

    @property
    def data_connector_query(
        self,
    ) -> dict:
        return self._data_connector_query

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def batch_spec_passthrough(self) -> dict:
        return self._batch_spec_passthrough

    def to_json_dict(self) -> dict:
        data_connector_query: Optional[dict] = None
        if self.data_connector_query is not None:
            data_connector_query = copy.deepcopy(self.data_connector_query)
            if data_connector_query.get("custom_filter_function") is not None:
                data_connector_query["custom_filter_function"] = data_connector_query[
                    "custom_filter_function"
                ].__name__

        json_dict: dict = {
            "datasource_name": self.datasource_name,
            "data_connector_name": self.data_connector_name,
            "data_asset_name": self.data_asset_name,
            "data_connector_query": data_connector_query,
        }

        if self.batch_spec_passthrough is not None:
            json_dict["batch_spec_passthrough"] = self.batch_spec_passthrough

        if self.limit is not None:
            json_dict["limit"] = self.limit

        if self.batch_identifiers is not None:
            json_dict["batch_identifiers"] = self.batch_identifiers

        if self.runtime_parameters is not None:
            key: str
            value: Any
            json_dict["runtime_parameters"] = {
                key: value
                for key, value in self.runtime_parameters.items()
                if key != "batch_data"
            }
            if self.runtime_parameters.get("batch_data") is not None:
                json_dict["runtime_parameters"]["batch_data"] = str(
                    type(self.runtime_parameters.get("batch_data"))
                )

        filter_properties_dict(properties=json_dict, clean_falsy=True, inplace=True)

        return json_dict

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2)

    @property
    def id(self) -> str:
        return IDDict(self.to_json_dict()).to_id()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            # Delegate comparison to the other instance's __eq__.
            return NotImplemented
        return self.id == other.id


class BatchRequest(BatchRequestBase):
    """
    This class contains all attributes of a batch_request.  See the comments in BatchRequestBase for design specifics.
    limit: refers to the number of batches requested (not rows per batch)
    """

    def __init__(
        self,
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        data_connector_query: Optional[dict] = None,
        limit: Optional[int] = None,
        batch_spec_passthrough: Optional[dict] = None,
    ):
        self._validate_init_parameters(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            data_connector_query=data_connector_query,
            limit=limit,
        )
        super().__init__(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            data_connector_query=data_connector_query,
            limit=limit,
            batch_spec_passthrough=batch_spec_passthrough,
        )

    @staticmethod
    def _validate_init_parameters(
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        data_connector_query: Optional[dict] = None,
        limit: Optional[int] = None,
    ):
        # TODO test and check all logic in this validator!
        if not (datasource_name and isinstance(datasource_name, str)):
            raise TypeError(
                f"""The type of an datasource name must be a string (Python "str").  The type given is
"{str(type(datasource_name))}", which is illegal.
            """
            )
        if not (data_connector_name and isinstance(data_connector_name, str)):
            raise TypeError(
                f"""The type of data_connector name must be a string (Python "str").  The type given is
"{str(type(data_connector_name))}", which is illegal.
                """
            )
        if not (data_asset_name and isinstance(data_asset_name, str)):
            raise TypeError(
                f"""The type of data_asset name must be a string (Python "str").  The type given is
        "{str(type(data_asset_name))}", which is illegal.
                        """
            )
        # TODO Abe 20201015: Switch this to DataConnectorQuery.
        if data_connector_query and not isinstance(data_connector_query, dict):
            raise TypeError(
                f"""The type of data_connector_query must be a dict object.  The type given is
"{str(type(data_connector_query))}", which is illegal.
                """
            )
        if limit and not isinstance(limit, int):
            raise TypeError(
                f"""The type of limit must be an integer (Python "int").  The type given is "{str(type(limit))}", which
is illegal.
                """
            )

    @staticmethod
    def _validate_runtime_batch_request_specific_init_parameters(
        runtime_parameters: dict,
        batch_identifiers: dict,
        batch_spec_passthrough: Optional[dict] = None,
    ):
        if not (runtime_parameters and (isinstance(runtime_parameters, dict))):
            raise TypeError(
                f"""The type for runtime_parameters must be a dict object.
                The type given is "{str(type(runtime_parameters))}", which is illegal."""
            )

        if not (batch_identifiers and isinstance(batch_identifiers, dict)):
            raise TypeError(
                f"""The type for batch_identifiers must be a dict object, with keys being identifiers defined in the
                data connector configuration.  The type given is "{str(type(batch_identifiers))}", which is illegal."""
            )

        if batch_spec_passthrough and not (isinstance(batch_spec_passthrough, dict)):
            raise TypeError(
                f"""The type for batch_spec_passthrough must be a dict object. The type given is \
"{str(type(batch_spec_passthrough))}", which is illegal.
"""
            )


class RuntimeBatchRequest(BatchRequest):
    def __init__(
        self,
        datasource_name: str,
        data_connector_name: str,
        data_asset_name: str,
        runtime_parameters: dict,
        batch_identifiers: dict,
        batch_spec_passthrough: Optional[dict] = None,
    ):
        super().__init__(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            batch_spec_passthrough=batch_spec_passthrough,
        )

        self._validate_runtime_batch_request_specific_init_parameters(
            runtime_parameters, batch_identifiers, batch_spec_passthrough
        )
        self._runtime_parameters = runtime_parameters
        self._batch_identifiers = batch_identifiers

    def __deepcopy__(self, memo):
        runtime_parameters = getattr(self, "_runtime_parameters", None)
        if isinstance(runtime_parameters, dict) and "batch_data" in runtime_parameters:
            batch_data = runtime_parameters.pop("batch_data")
            deepcopy_method = self.__deepcopy__
            self.__deepcopy__ = None
            cp = copy.deepcopy(self, memo)
            self.__deepcopy__ = deepcopy_method
            # Copy the function object
            func = types.FunctionType(
                deepcopy_method.__code__,
                deepcopy_method.__globals__,
                deepcopy_method.__name__,
                deepcopy_method.__defaults__,
                deepcopy_method.__closure__,
            )
            # Bind to cp and set
            bound_method = func.__get__(cp, cp.__class__)
            cp.__deepcopy__ = bound_method
            cp._runtime_parameters["batch_data"] = batch_data
            self._runtime_parameters["batch_data"] = batch_data
            return cp
        else:
            # Don't use custom deepcopy if batch_data isn't found
            self.__deepcopy__ = None
        return copy.deepcopy(self, memo)


# TODO: <Alex>The following class is to support the backward compatibility with the legacy design.</Alex>
class BatchMarkers(BatchKwargs):
    """A BatchMarkers is a special type of BatchKwargs (so that it has a batch_fingerprint) but it generally does
    NOT require specific keys and instead captures information about the OUTPUT of a datasource's fetch
    process, such as the timestamp at which a query was executed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "ge_load_time" not in self:
            raise InvalidBatchIdError("BatchMarkers requires a ge_load_time")

    @property
    def ge_load_time(self):
        return self.get("ge_load_time")


# TODO: <Alex>This module needs to be cleaned up.
#  We have Batch used for the legacy design, and we also need Batch for the new design.
#  However, right now, the Batch from the legacy design is imported into execution engines of the new design.
#  As a result, we have multiple, inconsistent versions of BatchMarkers, extending legacy/new classes.</Alex>
# TODO: <Alex>See also "great_expectations/datasource/types/batch_spec.py".</Alex>
class Batch(SerializableDictDot):
    def __init__(
        self,
        data,
        batch_request: BatchRequest = None,
        batch_definition: BatchDefinition = None,
        batch_spec: BatchSpec = None,
        batch_markers: BatchMarkers = None,
        # The remaining parameters are for backward compatibility.
        data_context=None,
        datasource_name=None,
        batch_parameters=None,
        batch_kwargs=None,
    ):
        self._data = data
        if batch_request is None:
            batch_request = {}
        self._batch_request = batch_request
        if batch_definition is None:
            batch_definition = IDDict()
        self._batch_definition = batch_definition
        if batch_spec is None:
            batch_spec = BatchSpec()
        self._batch_spec = batch_spec

        if batch_markers is None:
            batch_markers = BatchMarkers(
                {
                    "ge_load_time": datetime.datetime.now(
                        datetime.timezone.utc
                    ).strftime("%Y%m%dT%H%M%S.%fZ")
                }
            )
        self._batch_markers = batch_markers

        # The remaining parameters are for backward compatibility.
        self._data_context = data_context
        self._datasource_name = datasource_name
        self._batch_parameters = batch_parameters
        self._batch_kwargs = batch_kwargs or BatchKwargs()

    @property
    def data(self):
        return self._data

    @property
    def batch_request(self):
        return self._batch_request

    @batch_request.setter
    def batch_request(self, batch_request):
        self._batch_request = batch_request

    @property
    def batch_definition(self):
        return self._batch_definition

    @batch_definition.setter
    def batch_definition(self, batch_definition):
        self._batch_definition = batch_definition

    @property
    def batch_spec(self):
        return self._batch_spec

    @property
    def batch_markers(self):
        return self._batch_markers

    # The remaining properties are for backward compatibility.
    @property
    def data_context(self):
        return self._data_context

    @property
    def datasource_name(self):
        return self._datasource_name

    @property
    def batch_parameters(self):
        return self._batch_parameters

    @property
    def batch_kwargs(self):
        return self._batch_kwargs

    def to_json_dict(self) -> dict:
        json_dict: dict = {
            "data": str(self.data),
            "batch_request": self.batch_request.to_json_dict(),
            "batch_definition": self.batch_definition.to_json_dict()
            if isinstance(self.batch_definition, BatchDefinition)
            else {},
            "batch_spec": str(self.batch_spec),
            "batch_markers": str(self.batch_markers),
        }
        return json_dict

    @property
    def id(self):
        batch_definition = self._batch_definition
        return (
            batch_definition.id
            if isinstance(batch_definition, BatchDefinition)
            else batch_definition.to_id()
        )

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2)

    def head(self, n_rows=5, fetch_all=False):
        # FIXME - we should use a Validator after resolving circularity
        # Validator(self._data.execution_engine, batches=(self,)).get_metric(MetricConfiguration("table.head", {"batch_id": self.id}, {"n_rows": n_rows, "fetch_all": fetch_all}))
        metric = MetricConfiguration(
            "table.head",
            {"batch_id": self.id},
            {"n_rows": n_rows, "fetch_all": fetch_all},
        )
        return self._data.execution_engine.resolve_metrics((metric,))[metric.id]


def get_batch_request_from_acceptable_arguments(
    datasource_name: Optional[str] = None,
    data_connector_name: Optional[str] = None,
    data_asset_name: Optional[str] = None,
    *,
    batch_request: Optional[Union[BatchRequest, RuntimeBatchRequest]] = None,
    batch_data: Optional[Any] = None,
    data_connector_query: Optional[dict] = None,
    batch_identifiers: Optional[dict] = None,
    limit: Optional[int] = None,
    index: Optional[Union[int, list, tuple, slice, str]] = None,
    custom_filter_function: Optional[Callable] = None,
    batch_spec_passthrough: Optional[dict] = None,
    sampling_method: Optional[str] = None,
    sampling_kwargs: Optional[dict] = None,
    splitter_method: Optional[str] = None,
    splitter_kwargs: Optional[dict] = None,
    runtime_parameters: Optional[dict] = None,
    query: Optional[str] = None,
    path: Optional[str] = None,
    batch_filter_parameters: Optional[dict] = None,
    **kwargs,
) -> Union[BatchRequest, RuntimeBatchRequest]:
    """Obtain formal BatchRequest typed object from allowed attributes (supplied as arguments).
    This method applies only to the new (V3) Datasource schema.

    Args:
        batch_request

        datasource_name
        data_connector_name
        data_asset_name

        batch_request
        batch_data
        query
        path
        runtime_parameters
        data_connector_query
        batch_identifiers
        batch_filter_parameters

        limit
        index
        custom_filter_function

        sampling_method
        sampling_kwargs

        splitter_method
        splitter_kwargs

        batch_spec_passthrough

        **kwargs

    Returns:
        (BatchRequest) The formal BatchRequest object
    """

    if batch_request:
        if not isinstance(batch_request, BatchRequest):
            raise TypeError(
                f"batch_request must be an instance of BatchRequest object, not {type(batch_request)}"
            )
        datasource_name = batch_request.datasource_name

    # ensure that the first parameter is datasource_name, which should be a str. This check prevents users
    # from passing in batch_request as an unnamed parameter.
    if not isinstance(datasource_name, str):
        raise ge_exceptions.GreatExpectationsTypeError(
            f"the first parameter, datasource_name, must be a str, not {type(datasource_name)}"
        )

    if len([arg for arg in [batch_data, query, path] if arg is not None]) > 1:
        raise ValueError("Must provide only one of batch_data, query, or path.")

    if any(
        [
            batch_data is not None
            and runtime_parameters
            and "batch_data" in runtime_parameters,
            query and runtime_parameters and "query" in runtime_parameters,
            path and runtime_parameters and "path" in runtime_parameters,
        ]
    ):
        raise ValueError(
            "If batch_data, query, or path arguments are provided, the same keys cannot appear in the "
            "runtime_parameters argument."
        )

    if batch_request:
        # TODO: Raise a warning if any parameters besides batch_requests are specified
        return batch_request

    if any([batch_data is not None, query, path, runtime_parameters]):
        runtime_parameters = runtime_parameters or {}
        if batch_data is not None:
            runtime_parameters["batch_data"] = batch_data
        elif query is not None:
            runtime_parameters["query"] = query
        elif path is not None:
            runtime_parameters["path"] = path

        if batch_identifiers is None:
            batch_identifiers = kwargs
        else:
            # Raise a warning if kwargs exist
            pass

        batch_request = RuntimeBatchRequest(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            runtime_parameters=runtime_parameters,
            batch_identifiers=batch_identifiers,
            batch_spec_passthrough=batch_spec_passthrough,
        )
    else:
        if data_connector_query is None:
            if batch_filter_parameters is not None and batch_identifiers is not None:
                raise ValueError(
                    'Must provide either "batch_filter_parameters" or "batch_identifiers", not both.'
                )
            elif batch_filter_parameters is None and batch_identifiers is not None:
                logger.warning(
                    'Attempting to build data_connector_query but "batch_identifiers" was provided '
                    'instead of "batch_filter_parameters". The "batch_identifiers" key on '
                    'data_connector_query has been renamed to "batch_filter_parameters". Please update '
                    'your code. Falling back on provided "batch_identifiers".'
                )
                batch_filter_parameters = batch_identifiers
            elif batch_filter_parameters is None and batch_identifiers is None:
                batch_filter_parameters = kwargs
            else:
                # Raise a warning if kwargs exist
                pass

            data_connector_query_params: dict = {
                "batch_filter_parameters": batch_filter_parameters,
                "limit": limit,
                "index": index,
                "custom_filter_function": custom_filter_function,
            }
            data_connector_query = IDDict(data_connector_query_params)
        else:
            # Raise a warning if batch_filter_parameters or kwargs exist
            data_connector_query = IDDict(data_connector_query)

        if batch_spec_passthrough is None:
            batch_spec_passthrough = {}
            if sampling_method is not None:
                sampling_params: dict = {
                    "sampling_method": sampling_method,
                }
                if sampling_kwargs is not None:
                    sampling_params["sampling_kwargs"] = sampling_kwargs
                batch_spec_passthrough.update(sampling_params)
            if splitter_method is not None:
                splitter_params: dict = {
                    "splitter_method": splitter_method,
                }
                if splitter_kwargs is not None:
                    splitter_params["splitter_kwargs"] = splitter_kwargs
                batch_spec_passthrough.update(splitter_params)

        batch_request = BatchRequest(
            datasource_name=datasource_name,
            data_connector_name=data_connector_name,
            data_asset_name=data_asset_name,
            data_connector_query=data_connector_query,
            batch_spec_passthrough=batch_spec_passthrough,
        )

    return batch_request
