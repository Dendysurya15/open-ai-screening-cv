import json
import os
from datetime import datetime


def simplify_input_data(input_data):
    """Simplify candidate data to reduce token usage for AI evaluation."""
    kandidat = input_data["kandidat"][0]
    pengalaman = kandidat.get("pengalaman", {})

    # Limit non-formal education entries
    pendidikan = kandidat.get("pendidikan", {})
    if pendidikan and pendidikan.get("non_formal"):
        non_formal = pendidikan["non_formal"]
        if isinstance(non_formal, dict):
            limited_keys = list(non_formal.keys())[:3]
            pendidikan["non_formal"] = {key: non_formal[key] for key in limited_keys}
        elif isinstance(non_formal, list):
            pendidikan["non_formal"] = non_formal[:3]

    # Simplify work experience
    work_experience = pengalaman.get("pengalaman_pekerjaan", [])
    if work_experience:
        for exp in work_experience:
            if "jobdesk" in exp:
                exp["jobdesk"] = "\n".join(exp["jobdesk"].split("\n")[:3])
        work_experience = work_experience[:2]

    return {
        "lowongan_pekerjaan": input_data["lowongan_pekerjaan"],
        "key_pertanyaan_screening": input_data.get("key_pertanyaan_screening", ""),
        "kandidat": [
            {
                "id": kandidat["id"],
                "nama_lengkap": kandidat["nama_lengkap"],
                "pendidikan": pendidikan,
                "pengalaman": {
                    "pengalaman_pekerjaan": work_experience,
                    "tanggung_jawab_pada_pekerjaan_terakhir": pengalaman.get(
                        "tanggung_jawab_pada_pekerjaan_terakhir", ""
                    )[:200],
                },
                "jawaban_pertanyaan_skrining": kandidat.get(
                    "jawaban_pertanyaan_skrining", {}
                ),
            }
        ],
    }


def format_screening_result(screening_data, screening_id):
    """Format screening data to match the API output format."""
    try:
        key_screening = screening_data["screening_key_kategori"].split(",")
        summary_screening = json.loads(
            screening_data["summary_nilai_pertanyaan_screening"]
        )

        result = {
            "data": {
                "identities": {
                    "1": {
                        "kategori": "pendidikan",
                        "score": str(screening_data["nilai_pendidikan"]),
                        "comment": screening_data["summary_pendidikan"],
                    },
                    "2": {
                        "kategori": "pengalaman",
                        "score": str(screening_data["nilai_pengalaman"]),
                        "comment": screening_data["sumarry_pengalaman"],
                    },
                },
                "screening": {},
            },
            "screening_id": str(screening_id),
        }

        category_mapping = {
            "operasional_kebun": {
                "number": "1",
                "key": "jawaban_pertanyaan_skrining_operasional_kebun",
            },
            "general": {
                "number": "3",
                "key": "jawaban_pertanyaan_skrining_general",
            },
            "pernyataan": {
                "number": "4",
                "key": "jawaban_pertanyaan_skrining_pernyataan",
            },
            "supporting": {
                "number": "2",
                "key": "jawaban_pertanyaan_skrining_supporting",
            },
        }

        for category in key_screening:
            category = category.strip()
            if category in summary_screening:
                category_data = summary_screening[category]
                if (
                    category_data["nilai"] == "0"
                    and category_data["uraian"] == "Tidak ada penilaian"
                ):
                    continue

                mapping = category_mapping.get(category)
                if mapping:
                    result["data"]["screening"][mapping["number"]] = {
                        "kategori": mapping["key"],
                        "score": str(category_data["nilai"]),
                        "comment": category_data["uraian"],
                    }

        return result
    except Exception as e:
        print(f"Error formatting screening result: {str(e)}")
        return None


def save_screening_data(input_data, result, screening_id, test_mode=False):
    """Save screening input and result data to JSON files (test mode only)."""
    if not test_mode:
        return

    try:
        screening_dir = "screening_ai"
        if not os.path.exists(screening_dir):
            os.makedirs(screening_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        input_filepath = os.path.join(
            screening_dir, f"input_screening_{screening_id}_{timestamp}.json"
        )
        with open(input_filepath, "w", encoding="utf-8") as f:
            json.dump(input_data, f, indent=2, ensure_ascii=False)

        result_filepath = os.path.join(
            screening_dir, f"result_screening_{screening_id}_{timestamp}.json"
        )
        with open(result_filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\nTest Mode - Saved: {input_filepath}, {result_filepath}")

    except Exception as e:
        print(f"Error saving screening test data: {str(e)}")
