"""JSONL을 1회 스트리밍해 향 지도에 필요한 것만 캐시로 뽑는다.

perfumes.jsonl은 510MB라 매 실행마다 읽으면 느리다. 여기서 한 번만 읽고
MAP/cache/ 에 저장한 뒤 build_map.py가 그것을 쓴다.

뽑는 것:
  - people (JSONL 원본. CSV의 people은 null이 0으로 저장돼 있어 신뢰할 수 없다)
  - similar.reminds_me_of 간선 (평가 정답 라벨)
  - similar.also_liked 간선 (진단용)

원본 데이터는 읽기만 한다.
"""
import csv
import json
import os

MAP_DIR = os.path.dirname(os.path.abspath(__file__))
JSONL = os.path.join(MAP_DIR, "perfumes.jsonl")
CACHE = os.path.join(MAP_DIR, "cache")

# reminds_me_of는 전부 저장한다. Step 1의 known-answer test가 EDA 04의
# relevant pair 구축을 그대로 재현해야 하는데, 거기서는 전체 간선을 쓴다.
# also_liked는 진단용일 뿐이라 후보 풀 근처만 있으면 된다.
EDGE_SOURCE_MIN_PEOPLE = 0
ALSO_LIKED_MIN_PEOPLE = 200


def main():
    os.makedirs(CACHE, exist_ok=True)

    n_lines = 0
    n_people_null = 0
    people_rows = []
    remind_rows = []
    also_rows = []

    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            n_lines += 1
            d = json.loads(line)
            pid = d.get("id")
            people = d.get("people")
            if people is None:
                n_people_null += 1
            people_rows.append((pid, "" if people is None else people))

            sim = d.get("similar") or {}
            for x in sim.get("reminds_me_of") or []:
                remind_rows.append(
                    (pid, x.get("id"), x.get("up_votes") or 0, x.get("down_votes") or 0)
                )
            if (people or 0) >= ALSO_LIKED_MIN_PEOPLE:
                for x in sim.get("also_liked") or []:
                    also_rows.append((pid, x.get("id")))

    def write(name, header, rows):
        path = os.path.join(CACHE, name)
        with open(path, "w", newline="", encoding="utf-8") as fo:
            w = csv.writer(fo)
            w.writerow(header)
            w.writerows(rows)
        return path

    write("people.csv", ["id", "people"], people_rows)
    write("reminds_edges.csv", ["src", "dst", "up_votes", "down_votes"], remind_rows)
    write("also_liked_edges.csv", ["src", "dst"], also_rows)

    print(f"lines read            : {n_lines}")
    print(f"people is null        : {n_people_null}  ({100*n_people_null/n_lines:.2f}%)")
    print(f"reminds edges (전체)  : {len(remind_rows)}")
    print(f"also_liked edges (src people>={ALSO_LIKED_MIN_PEOPLE}) : {len(also_rows)}")
    print(f"cache written to      : {CACHE}")


if __name__ == "__main__":
    main()
