import json
import time

import orjson


def main() -> None:

    data = """{
  "actionPoints": [
    {
      "id": "acp_12d3c6ea8e2c45be9e555317a500f05e",
      "name": "global_ap",
      "parent": "",
      "position": {
        "x": -0.2706979,
        "y": -0.01389605,
        "z": 0.03940087
      },
      "orientations": [],
      "robotJoints": [],
      "actions": [
        {
          "id": "act_8a3927ef31854d019fee01bd35b1db14",
          "name": "random_integer",
          "type": "obj_e06eff6c32e44b87a434ac9dba807af4/random_integer",
          "parameters": [
            {
              "name": "range_min",
              "type": "integer",
              "value": "0"
            },
            {
              "name": "range_max",
              "type": "integer",
              "value": "25"
            }
          ],
          "flows": [
            {
              "type": "default",
              "outputs": [
                "random_integer_integer"
              ]
            }
          ]
        },
        {
          "id": "act_66dee6d40ed4441cb20df39a644c2142",
          "name": "random_double",
          "type": "obj_e06eff6c32e44b87a434ac9dba807af4/random_double",
          "parameters": [
            {
              "name": "range_min",
              "type": "double",
              "value": "-100.0"
            },
            {
              "name": "range_max",
              "type": "double",
              "value": "1000.0"
            }
          ],
          "flows": [
            {
              "type": "default",
              "outputs": [
                "random_double_double"
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "acp_d188ee7041b543448d5b5a95ef9b31f8",
      "name": "global_ap_2",
      "parent": "",
      "position": {
        "x": -0.1229082,
        "y": -0.1421725,
        "z": 0.0729487
      },
      "orientations": [],
      "robotJoints": [],
      "actions": [
        {
          "id": "act_50dc51dcecf84f668943d50ab1496080",
          "name": "homee",
          "type": "obj_eae63bcba8a6480f9f0d835c79faff7a/home",
          "parameters": [],
          "flows": [
            {
              "type": "default",
              "outputs": []
            }
          ]
        }
      ]
    },
    {
      "id": "acp_1d7b068e52a045a38c5e229bd9e67b51",
      "name": "global_ap_3",
      "parent": "",
      "position": {
        "x": -0.3215979,
        "y": 0.07241742,
        "z": -0.1127059
      },
      "orientations": [],
      "robotJoints": [],
      "actions": []
    },
    {
      "id": "acp_a02580bfd52c44089a364d3bd72d11fa",
      "name": "global_ap_2_ap",
      "parent": "acp_d188ee7041b543448d5b5a95ef9b31f8",
      "position": {
        "x": -0.02957418,
        "y": 0.2778401,
        "z": -0.260891
      },
      "orientations": [],
      "robotJoints": [],
      "actions": []
    },
    {
      "id": "acp_6be31ab143d94ba6a8e19f10eb373b1f",
      "name": "global_ap_4",
      "parent": "",
      "position": {
        "x": -0.1743033,
        "y": 0.1288419,
        "z": -0.1200256
      },
      "orientations": [],
      "robotJoints": [],
      "actions": []
    }
  ],
  "sceneId": "scn_630591d5958f4f9aaea3031f59737054",
  "hasLogic": true,
  "parameters": [
    {
      "id": "fdfsdfds",
      "name": "prom2",
      "type": "integer",
      "value": "0"
    },
    {
      "id": "erere",
      "name": "boolprom",
      "type": "boolean",
      "value": "true"
    },
    {
      "id": "fdsfsdfsdfdfsd",
      "name": "prom2",
      "type": "string",
      "value": "whatever"
    }
  ],
  "functions": [],
  "logic": [
    {
      "id": "lit_24d3bfe92ca7473699156fa627dfda5a",
      "start": "START",
      "end": "act_8a3927ef31854d019fee01bd35b1db14"
    },
    {
      "id": "lit_7a694565bcfe4b4fbfa181cfe5db5222",
      "start": "act_8a3927ef31854d019fee01bd35b1db14",
      "end": "act_66dee6d40ed4441cb20df39a644c2142"
    },
    {
      "id": "lit_c566e3a0e24547aaabafad3796ed9312",
      "start": "act_66dee6d40ed4441cb20df39a644c2142",
      "end": "act_50dc51dcecf84f668943d50ab1496080"
    },
    {
      "id": "lit_b1e824d1580d4e10ac91e72627826fcd",
      "start": "act_50dc51dcecf84f668943d50ab1496080",
      "end": "END"
    }
  ],
  "objectOverrides": [],
  "id": "pro_57606ed3332d4f7eb8f2c628d56a53a1",
  "name": "tst",
  "description": "",
  "created": "2021-06-09T08:50:33.599446+00:00",
  "modified": "2021-07-01T14:06:25.932292+00:00"
}"""

    iterations = 1000

    d = json.loads(data)
    comp_data = json.dumps(d)  # compact data (not pretty-printed)

    for lib in (json, orjson):
        start = time.monotonic()
        for _ in range(iterations):
            lib.loads(data)
        end = time.monotonic()

        print(f"{lib.__name__}.loads: {(end-start)*1000:.3f}ms")

    print()

    for lib in (json, orjson):
        start = time.monotonic()
        for _ in range(iterations):
            lib.loads(comp_data)
        end = time.monotonic()

        print(f"{lib.__name__}.loads (comp): {(end-start)*1000:.3f}ms")

    print()

    start = time.monotonic()
    for _ in range(iterations):
        json.dumps(d)
    end = time.monotonic()

    print(f"{json.__name__}.dumps: {(end-start)*1000:.3f}ms")

    start = time.monotonic()
    for _ in range(iterations):
        orjson.dumps(d).decode()
    end = time.monotonic()

    print(f"{orjson.__name__}.dumps: {(end - start) * 1000:.3f}ms")


if __name__ == "__main__":
    main()
