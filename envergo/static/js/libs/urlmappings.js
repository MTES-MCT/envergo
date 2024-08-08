/**
 * Url mapping creation API.
 *
 * This module provides a class to create a short URL for evaluations.
 *
 * Post a url, got a short one in response.
 *
 * const mapping = new UrlMapping();
 * mapping.create("https://www.example.com").then((json) => {
 *   console.log(json.short_url);
 * });
 */
(function (exports) {
  "use strict";

  const UrlMapping = function () { };
  exports.UrlMapping = UrlMapping;

  UrlMapping.prototype.create = async function (url) {
    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };
    let formData = new FormData();
    formData.append('url', url);

    let response = await fetch(MAPPING_CREATE_URL, { headers: headers, method: "POST", body: formData });
    let data = await response.json();

    // The http request got a response != 2XX
    if (!response.ok) {
      const message = JSON.stringify(data);
      throw new Error(message);
    }

    return data;
  };

})(this);
