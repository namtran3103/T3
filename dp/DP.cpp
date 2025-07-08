#pragma clang diagnostic push
#pragma ide diagnostic ignored "modernize-use-nodiscard"
//---------------------------------------------------------------------------
#include "lleaves_header.hpp"
#include <bit>
#include <cassert>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <span>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <vector>
#include <LightGBM/c_api.h>
//---------------------------------------------------------------------------
namespace fs = std::filesystem;
//---------------------------------------------------------------------------
struct BitsetIterator {
    uint64_t set;
    uint64_t operator*() const { return std::countr_zero(set); }
    void operator++() { set &= set - 1; }
    static BitsetIterator end() { return BitsetIterator{0}; }
    auto operator<=>(const BitsetIterator& other) const = default;
};
//---------------------------------------------------------------------------
bool isSubset(uint64_t candidateSubset, uint64_t candidateSuperset) {
    return candidateSubset == (candidateSubset & candidateSuperset);
}
//---------------------------------------------------------------------------
uint64_t fullBitset(uint64_t n) {
    return (1ull << n) - 1;
}
//---------------------------------------------------------------------------
void split_string_view(std::string_view str, std::vector<std::string_view>& result) {
    result.clear();
    size_t start = 0;
    size_t end = 0;
    while (end != std::string_view::npos) {
        end = str.find(' ', start);
        if (end != std::string_view::npos) {
            result.emplace_back(str.substr(start, end - start));
        } else {
            result.emplace_back(str.substr(start));
        }
        start = end + 1;
    }
}
//---------------------------------------------------------------------------
uint64_t parseInt(std::string_view sv) {
    uint64_t res{};
    auto ret = std::from_chars(sv.data(), sv.data() + sv.size(), res);
    if (ret.ec == std::errc::invalid_argument) {
        std::cout << "could not load " << sv << " as int\n";
    }
    return res;
}
//---------------------------------------------------------------------------
double parseDouble(std::string_view sv) {
    double res{};
    auto ret = std::from_chars(sv.data(), sv.data() + sv.size(), res);
    if (ret.ec == std::errc::invalid_argument) {
        std::cout << "could not load " << sv << " as double\n";
    }
    return res;
}
//---------------------------------------------------------------------------
struct Features {
    double TableScan_Scan_const;
    double TableScan_Scan_in_card;
    double TableScan_Scan_out_percentage;
    double TableScan_Scan_empty_output;

    double HashJoin_Build_const;
    double HashJoin_Build_out_card;
    double HashJoin_Build_out_size;
    double HashJoin_Build_in_percentage;

    double HashJoin_Probe_const;
    double HashJoin_Probe_in_card;
    double HashJoin_Probe_right_percentage;
    double HashJoin_Probe_out_percentage;

    void add_to_vector(std::span<double> vec) const;
    void operator+=(const Features& other);
    void print() const;
};
//---------------------------------------------------------------------------
void Features::add_to_vector(std::span<double> vec) const {
    vec[0] += TableScan_Scan_const;
    vec[1] += TableScan_Scan_in_card;
    vec[3] += TableScan_Scan_out_percentage;
    vec[5] += 1.0; // TableScan_Scan_compare_percentage is always set to 1, so we have a plausible filter
    vec[10] += TableScan_Scan_empty_output;

    vec[39] += HashJoin_Build_const;
    vec[40] += HashJoin_Build_out_card;
    vec[41] += HashJoin_Build_out_size;
    vec[42] += HashJoin_Build_in_percentage;

    vec[43] += HashJoin_Probe_const;
    vec[44] += HashJoin_Probe_in_card;
    vec[45] += HashJoin_Probe_right_percentage;
    vec[46] += HashJoin_Probe_out_percentage;
}
//---------------------------------------------------------------------------
void Features::operator+=(const Features& o) {
    TableScan_Scan_const += o.TableScan_Scan_const;
    TableScan_Scan_in_card += o.TableScan_Scan_in_card;
    TableScan_Scan_out_percentage += o.TableScan_Scan_out_percentage;
    TableScan_Scan_empty_output += o.TableScan_Scan_empty_output;

    HashJoin_Build_const += HashJoin_Build_const;
    HashJoin_Build_out_card += HashJoin_Build_out_card;
    HashJoin_Build_out_size += HashJoin_Build_out_size;
    HashJoin_Build_in_percentage += HashJoin_Build_in_percentage;

    HashJoin_Probe_const += HashJoin_Probe_const;
    HashJoin_Probe_in_card += HashJoin_Probe_in_card;
    HashJoin_Probe_right_percentage += HashJoin_Probe_right_percentage;
    HashJoin_Probe_out_percentage += HashJoin_Probe_out_percentage;
}
//---------------------------------------------------------------------------
void Features::print() const {
    std::array<double, 110> vec{};
    add_to_vector(vec);
    auto& wrtr = std::cout;
    wrtr << "[";
    for (const auto& x : vec) {
        wrtr << x << ", ";
    }
    wrtr << "],\n";
}
//---------------------------------------------------------------------------
struct Model {
    BoosterHandle booster;
    FastConfigHandle config;
    std::vector<double> data;
    std::vector<double> out;
    static constexpr uint64_t nFeatures = 110;
    uint64_t currentlyFilled = 0;
    uint64_t callsToPredict = 0;

    void loadModel(const fs::path& path);
    void prepare();
    void predictMany();
    void predictManyST();
    double predict();
    double predictCompiled();
    void predictManyCompiled();
    void resize(uint64_t n);
    double* registerFeatures(const Features& features);
    void resetInput();
};
//---------------------------------------------------------------------------
void Model::loadModel(const fs::path& path) {
    int iterations;
    int status = LGBM_BoosterCreateFromModelfile(path.c_str(), &iterations, &booster);
    if (status) {
        std::cout << "Could not load model" << std::endl;
    }
}
//---------------------------------------------------------------------------
void Model::predictMany() {
    int64_t outLen;
    LGBM_BoosterPredictForMat(
        booster,
        data.data(),
        C_API_DTYPE_FLOAT64,
        static_cast<int>(currentlyFilled),
        static_cast<int>(nFeatures),
        1,
        C_API_PREDICT_NORMAL,
        0,
        0,
        "",
        &outLen,
        out.data());
    assert(outLen == currentlyFilled);
    // actually compute the correct output
    for (uint64_t i = 0; i < currentlyFilled; ++i) {
        // The running time in ms is exp(-y) * table_size
        out[i] = std::exp(-out[i]) * data[i * nFeatures + 1];
    }
    resetInput();
    currentlyFilled = 0;
    ++callsToPredict;
}
//---------------------------------------------------------------------------
void Model::predictManyST() {
    int64_t outLen;
    int previousThreadCount;
    LGBM_GetMaxThreads(&previousThreadCount);
    LGBM_SetMaxThreads(1);
    LGBM_BoosterPredictForMat(
        booster,
        data.data(),
        C_API_DTYPE_FLOAT64,
        static_cast<int>(currentlyFilled),
        static_cast<int>(nFeatures),
        1,
        C_API_PREDICT_NORMAL,
        0,
        0,
        "",
        &outLen,
        out.data());
    assert(outLen == currentlyFilled);
    // actually compute the correct output
    for (uint64_t i = 0; i < currentlyFilled; ++i) {
        // The running time in ms is exp(-y) * table_size
        out[i] = std::exp(-out[i]) * data[i * nFeatures + 1];
    }
    resetInput();
    currentlyFilled = 0;
    ++callsToPredict;
    LGBM_SetMaxThreads(previousThreadCount);
}
//---------------------------------------------------------------------------
double Model::predict() {
    assert(config);
    int64_t outLen;
    LGBM_BoosterPredictForMatSingleRowFast(
        config,
        data.data(),
        &outLen,
        out.data());
    assert(outLen == currentlyFilled);
    // actually compute the correct output
    // The running time in ms is exp(-y) * table_size
    out[0] = std::exp(-out[0]) * data[1];
    resetInput();
    currentlyFilled = 0;
    ++callsToPredict;
    return out[0];
}
//---------------------------------------------------------------------------
double Model::predictCompiled() {
    forest_root(data.data(), out.data(), 0, 1);
    out[0] = std::exp(-out[0]) * data[1];
    resetInput();
    currentlyFilled = 0;
    ++callsToPredict;
    return out[0];
}
//---------------------------------------------------------------------------
void processChunk(std::vector<double>& data, std::vector<double>& out, uint64_t start, uint64_t end, int nFeatures) {
    int nCurrent = static_cast<int>(end - start);
    forest_root(data.data(), out.data(), static_cast<int>(start), nCurrent);
    for (uint64_t i = start; i < end; ++i) {
        out[i] = std::exp(-out[i]) * data[i * nFeatures + 1];
    }
}
//---------------------------------------------------------------------------
void Model::predictManyCompiled() {
    forest_root(data.data(), out.data(), 0, static_cast<int>(currentlyFilled));
    for (uint64_t i = 0; i < currentlyFilled; ++i) {
        out[i] = std::exp(-out[i]) * data[i * nFeatures + 1];
    }
    resetInput();
    currentlyFilled = 0;
    ++callsToPredict;
}
//---------------------------------------------------------------------------
void Model::resize(uint64_t n) {
    data.resize(n * nFeatures);
    out.resize(n);
}
//---------------------------------------------------------------------------
double* Model::registerFeatures(const Features& features) {
    assert(currentlyFilled < out.size());
    assert(out.size() * nFeatures == data.size());
    double* begin = data.data() + currentlyFilled * nFeatures;
    double* result = out.data() + currentlyFilled;
    ++currentlyFilled;
    features.add_to_vector(std::span<double>(begin, nFeatures));
    return result;
}
//---------------------------------------------------------------------------
void Model::resetInput() {
    std::memset(data.data(), 0, data.size() * sizeof(double));
    currentlyFilled = 0;
}
//---------------------------------------------------------------------------
void Model::prepare() {
    auto status = LGBM_BoosterPredictForMatSingleRowFastInit(
        booster,
        C_API_PREDICT_NORMAL,
        0,
        0,
        C_API_DTYPE_FLOAT64,
        static_cast<int>(nFeatures),
        "",
        &config);
    assert(!status);
}
//---------------------------------------------------------------------------
struct Relation {
    std::string name;
    uint64_t id;
    double table_size;
    double cardinality; // The number of tuples actually selected from the table
};
//---------------------------------------------------------------------------
struct NamedJoin {
    std::string left;
    std::string right;
    double selectivity;
};
//---------------------------------------------------------------------------
struct Join {
    uint64_t left; // bitset of left relations
    uint64_t right; // bitset of right relations
    double selectivity;

    bool canJoin(uint64_t leftSet, uint64_t rightSet, bool& swapped) const;
};
//---------------------------------------------------------------------------
bool Join::canJoin(uint64_t leftSet, uint64_t rightSet, bool& swapped) const {
    if (isSubset(left, leftSet) && isSubset(right, rightSet)) {
        swapped = false;
        return true;
    }
    if (isSubset(left, rightSet) && isSubset(right, leftSet)) {
        swapped = true;
        return true;
    }
    return false;
}
//---------------------------------------------------------------------------
struct Cardinality {
    uint64_t relations; // bitset representation of relations
    uint64_t cardinality;
};
//---------------------------------------------------------------------------
struct QueryGraph {
    std::vector<Relation> relations;
    std::vector<Join> joins;
    std::unordered_map<uint64_t, double> cardinalities;
    std::vector<std::vector<const Join*>> joinLookup;

    bool isConnected(uint64_t leftClass, uint64_t rightClass) const;
    void prepareLookup();
};
//---------------------------------------------------------------------------
bool QueryGraph::isConnected(uint64_t leftClass, uint64_t rightClass) const {
    auto [smaller, larger] = (std::popcount(leftClass) < std::popcount(rightClass)) ? std::pair{leftClass, rightClass} : std::pair{rightClass, leftClass};
    for (auto it = BitsetIterator{smaller}, end = BitsetIterator::end(); it != end; ++it) {
        for (const auto& j : joinLookup[*it]) {
            bool swapped;
            if (j->canJoin(leftClass, rightClass, swapped)) {
                return true;
            }
        }
    }
    return false;
}
//---------------------------------------------------------------------------
void QueryGraph::prepareLookup() {
    joinLookup.resize(relations.size());
    for (const auto& j : joins) {
        joinLookup[std::countr_zero(j.left)].push_back(&j);
        joinLookup[std::countr_zero(j.right)].push_back(&j);
    }
}
//---------------------------------------------------------------------------
QueryGraph parseDump(const fs::path& filename) {
    QueryGraph result;

    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cout << "could not find " << filename << std::endl;
        return result;
    }

    std::vector<Relation> relations;
    std::vector<NamedJoin> joins;
    std::vector<Cardinality> cardinalities;

    bool read = false;
    bool seenJoin = false;

    std::string line;
    std::vector<std::string_view> elements;
    while (std::getline(file, line)) {
        std::string_view line_view(line);
        split_string_view(line_view, elements);
        if (elements.empty()) continue;
        if (elements[0] == "input") {
            if (seenJoin) read = true;
            if (read) {
                // std::cout << line_view << std::endl;
                relations.push_back(Relation{
                    std::string(elements[4]),
                    parseInt(elements[1]),
                    parseDouble(elements[3]),
                    parseDouble(elements[2]),
                });
            }
        } else if (elements[0] == "join") {
            seenJoin = true;
            if (read) {
                // std::cout << line_view << std::endl;
                joins.push_back(NamedJoin{
                    std::string(elements[1].substr(6, elements[1].size() - 7)),
                    std::string(elements[2].substr(7, elements[2].size() - 8)),
                    parseDouble(elements[3].substr(4))});
            }
        } else if (elements[0] == "o") {
            if (read) {
                // std::cout << line_view << std::endl;
                cardinalities.push_back(Cardinality{
                    parseInt(elements[1]),
                    parseInt(elements[2]),
                });
            }
        }
    }
    file.close();

    std::unordered_map<std::string, uint64_t> relationLookup;
    for (const auto& r : relations) {
        relationLookup[r.name] = 1ull << r.id;
    }
    for (const auto& j : joins) {
        assert(relationLookup.find(j.left) != relationLookup.end());
        assert(relationLookup.find(j.right) != relationLookup.end());
        result.joins.push_back(Join{relationLookup[j.left], relationLookup[j.right], j.selectivity});
    }

    result.relations = std::move(relations);
    for (const auto& card : cardinalities) {
        result.cardinalities[card.relations] = static_cast<double>(card.cardinality);
    }

    return result;
}
//---------------------------------------------------------------------------
std::vector<fs::path> get_files() {
    std::vector<fs::path> result;
    fs::path directory("./dp/data");
    for (const auto& entry : fs::directory_iterator(directory)) {
        if (fs::is_regular_file(entry.path())) {
            result.push_back(entry.path());
        }
    }
    return result;
}
//---------------------------------------------------------------------------
// Plans for our cost model
struct Plan {
    Features openPipelineFeatures; // The features of the one pipeline that is currently not finished yet (rightmost)
    Plan* left;
    Plan* right;
    double cardinality;
    double cost;
    double matCost; // Cost of all pipelines except the currently open one
    int64_t relation; // Index of the relation of a base table; -1 for non-base-tables

    Features tableScanFeatures(const Relation& rel) const;
    Features buildHashTable() const; //  Take the current sub-plan and end it in a hash table build
};
//---------------------------------------------------------------------------
Features Plan::tableScanFeatures(const Relation& rel) const {
    Features res{};
    assert(relation >= 0);
    res.TableScan_Scan_const = 1;
    res.TableScan_Scan_in_card = rel.table_size;
    res.TableScan_Scan_out_percentage = rel.cardinality / rel.table_size;
    res.TableScan_Scan_empty_output = rel.cardinality == 0;
    return res;
}
//---------------------------------------------------------------------------
Features Plan::buildHashTable() const {
    Features result = openPipelineFeatures;
    assert(result.HashJoin_Build_const == 0);
    result.HashJoin_Build_const += 1;
    result.HashJoin_Build_out_card += cardinality;
    result.HashJoin_Build_out_size += 16;
    // if (result.TableScan_Scan_in_card == 0) {
    //     std::cout << "oops\n";
    // }
    result.HashJoin_Build_in_percentage += cardinality / result.TableScan_Scan_in_card;
    return result;
}
//---------------------------------------------------------------------------
Features getProbeFeatures(Plan* probeSide, Plan* buildSide, double outCardinality) {
    Features result = probeSide->openPipelineFeatures;
    result.HashJoin_Probe_const += 1;
    result.HashJoin_Probe_in_card += buildSide->cardinality;
    result.HashJoin_Probe_right_percentage += probeSide->cardinality / result.TableScan_Scan_in_card;
    result.HashJoin_Probe_out_percentage += outCardinality / result.TableScan_Scan_in_card;
    return result;
}
//---------------------------------------------------------------------------
// Plans for cout
struct Plan1 {
    Plan1* left;
    Plan1* right;
    double cardinality;
    double cost;
    int64_t relation; // Index of the relation of a base table; -1 for non-base-tables
};
//---------------------------------------------------------------------------
template <typename T>
class BumpAllocator {
    std::vector<void*> chunks;
    uint64_t remainingSlots = 0;
    uint64_t nextChunkSize = 8;

    public:
    BumpAllocator() = default;
    BumpAllocator(const BumpAllocator&) = delete;
    BumpAllocator(const BumpAllocator&&) = delete;
    ~BumpAllocator();
    T* alloc();
    void release();
};
//---------------------------------------------------------------------------
template <typename T>
BumpAllocator<T>::~BumpAllocator() {
    release();
}
//---------------------------------------------------------------------------
template <typename T>
void BumpAllocator<T>::release() {
    for (void* chunk : chunks) {
        std::free(chunk);
    }
    remainingSlots = 0;
    nextChunkSize = 8;
    chunks = {};
}
//---------------------------------------------------------------------------
template <typename T>
T* BumpAllocator<T>::alloc() {
    if (remainingSlots == 0) [[unlikely]] {
        chunks.push_back(std::aligned_alloc(alignof(T), sizeof(T) * nextChunkSize));
        remainingSlots = nextChunkSize;
        nextChunkSize *= 2;
    }
    T* slot = static_cast<T*>(chunks.back()) + remainingSlots - 1;
    --remainingSlots;
    return slot;
}
//---------------------------------------------------------------------------
// using Plan = Plan;
//---------------------------------------------------------------------------
struct CostModelReturnVal {
    Features openPipelineFeatures; // Features of the current pipeline
    double cost; // Cost of the full join tree
    double matCost; // Cost of all pipelines except the on that is still open
};
//---------------------------------------------------------------------------
CostModelReturnVal cost_cout(Plan* leftPlan, Plan* rightPlan, double card, Model& model) {
    CostModelReturnVal res{};
    res.cost = card + leftPlan->cost + rightPlan->cost;
    ++model.callsToPredict;
    return res;
}
//---------------------------------------------------------------------------
CostModelReturnVal cost_model(Plan* leftPlan, Plan* rightPlan, double outCard, Model& model) {
    CostModelReturnVal res{};
    Features buildFeatures = leftPlan->buildHashTable();
    model.registerFeatures(buildFeatures);
    double leftBuildCost = model.predictCompiled();
    Features probeFeatures = getProbeFeatures(rightPlan, leftPlan, outCard);
    model.registerFeatures(probeFeatures);
    double probeCost = model.predictCompiled();
    res.matCost = leftPlan->matCost + rightPlan->matCost + leftBuildCost;
    res.cost = res.matCost + probeCost;
    res.openPipelineFeatures = probeFeatures;
    return res;
}
//---------------------------------------------------------------------------
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
class PlanGenerator {
    // Mapping from bitset of relations to plan
    std::unordered_map<uint64_t, Plan*> plans;
    // Fast allocator for plans
    BumpAllocator<Plan> allocator;
    // Model for cost prediction
    Plan* createBaseTablePlan(const Relation& relation);
    Plan* createPlan(Plan* left, Plan* right);

    public:
    Model* model = nullptr;
    PlanGenerator() = default;
    // Insert base tables into DP table
    void seedBaseTables(const QueryGraph& q);
    // Run DPSize
    Plan* runDPSize(const QueryGraph& q);
    // Create new join tree if better. Returns, newly allocated plans (not updated plans)
    Plan* createJoinTree(uint64_t leftClass, Plan* leftPlan, uint64_t rightClass, Plan* rightPlan, const QueryGraph& q);
};
//---------------------------------------------------------------------------
#pragma clang diagnostic push
#pragma ide diagnostic ignored "MemoryLeak"
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
void PlanGenerator<CostFn>::seedBaseTables(const QueryGraph& q) {
    for (uint64_t i = 0; i < q.relations.size(); ++i) {
        uint64_t problem = 1ull << i;
        Plan* plan = createBaseTablePlan(q.relations[i]);
        plans[problem] = plan;
    }
}
#pragma clang diagnostic pop
//---------------------------------------------------------------------------
#pragma clang diagnostic push
#pragma ide diagnostic ignored "MemoryLeak"
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
Plan* PlanGenerator<CostFn>::createBaseTablePlan(const Relation& relation) {
    Plan* plan = allocator.alloc();
    new (plan) Plan{Features{}, nullptr, nullptr, relation.cardinality, 0, 0, static_cast<int64_t>(relation.id)};
    plan->openPipelineFeatures = plan->tableScanFeatures(relation);
    return plan;
}
#pragma clang diagnostic pop
//---------------------------------------------------------------------------
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
Plan* PlanGenerator<CostFn>::createPlan(Plan* left, Plan* right) {
    Plan* plan = allocator.alloc();
    new (plan) Plan{
        right->openPipelineFeatures, left, right, std::numeric_limits<double>::max(),
        std::numeric_limits<double>::max(), -1};
    return plan;
}
//---------------------------------------------------------------------------
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
Plan* PlanGenerator<CostFn>::runDPSize(const QueryGraph& q) {
    assert(model);
    seedBaseTables(q);
    // Problem list of sizes
    std::vector<std::vector<uint64_t>> sizes;
    sizes.resize(q.relations.size() + 1);
    for (const auto& r : q.relations) {
        sizes[1].push_back(1ull << r.id);
    }
    for (uint64_t size = 2; size <= q.relations.size(); ++size) {
        for (uint64_t leftSize = 1; leftSize < size; ++leftSize) {
            for (uint64_t leftClass : sizes[leftSize]) {
                Plan* leftPlan = plans[leftClass];
                assert(leftPlan);
                for (const auto& rightClass : sizes[size - leftSize]) {
                    if (leftClass & rightClass) continue;
                    Plan* rightPlan = plans[rightClass];
                    assert(rightPlan);
                    auto* newTree = createJoinTree(leftClass, leftPlan, rightClass, rightPlan, q);
                    if (newTree) {
                        sizes[size].push_back(leftClass | rightClass);
                    }
                }
            }
        }
    }
    uint64_t allRelationsBitset = fullBitset(q.relations.size());
    assert(plans.find(allRelationsBitset) != plans.end());
    return plans[allRelationsBitset];
}
//---------------------------------------------------------------------------
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
Plan* PlanGenerator<CostFn>::createJoinTree(
    uint64_t leftClass, Plan* leftPlan,
    uint64_t rightClass, Plan* rightPlan,
    const QueryGraph& q) {
    bool allocated = false;
    uint64_t newClass = leftClass | rightClass;
    auto previousEntryIt = plans.find(newClass);
    Plan* entry = nullptr;
    if (previousEntryIt != plans.end()) {
        entry = previousEntryIt->second;
    }
    if (!entry) {
        if (!q.isConnected(leftClass, rightClass)) {
            return nullptr;
        }
        entry = createPlan(leftPlan, rightPlan);
        plans[newClass] = entry;
        allocated = true;
    }
    double card = q.cardinalities.find(newClass)->second;
    // auto modelReturnVal = cost_cout(leftPlan, rightPlan, card, *model);
    CostModelReturnVal modelReturnVal = CostFn(leftPlan, rightPlan, card, *model);
    if (modelReturnVal.cost < entry->cost) {
        entry->left = leftPlan;
        entry->right = rightPlan;
        entry->cost = modelReturnVal.cost;
        entry->cardinality = card;
        entry->openPipelineFeatures = modelReturnVal.openPipelineFeatures;
        entry->matCost = modelReturnVal.matCost;
    }

    return allocated ? entry : nullptr;
}
//---------------------------------------------------------------------------
std::string printPlan(const Plan* plan, const QueryGraph& q) {
    if (!plan->left) {
        assert(!plan->right);
        return "(" + q.relations[plan->relation].name + ")";
    }
    return "(" + printPlan(plan->left, q) + "⋈" + printPlan(plan->right, q) + ")";
}
//---------------------------------------------------------------------------
template <CostModelReturnVal (*CostFn)(Plan*, Plan*, double, Model&)>
void runModel(const fs::path& outPath, Model model, std::vector<QueryGraph> qs,
              const std::vector<std::string>& names, std::ofstream& tbl) {
    std::ofstream planFile(outPath);
    auto begin = std::chrono::high_resolution_clock::now();
    for (uint64_t i = 0; i < qs.size(); ++i) {
        auto currentBegin = std::chrono::high_resolution_clock::now();
        QueryGraph& q = qs[i];
        q.prepareLookup();
        PlanGenerator<CostFn> pg;
        pg.model = &model;
        Plan* best = pg.runDPSize(q);
        auto currentEnd = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> duration = currentEnd - currentBegin;
        // std::cout << names[i] << " cost: " << best->cost << ", time: " << duration.count() << "ms ";
        planFile << names[i] << "\n"
                 << printPlan(best, q) << "\n";
    }
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> duration = end - begin;

    // std::cout << "\n" << model.callsToPredict << " calls to predict in " << duration.count() << "ms, "
    //           << static_cast<double>(duration.count()) / static_cast<double>(model.callsToPredict) <<
    //           "ms per predict " << std::endl;
    tbl << std::setprecision(1) << duration.count() << "ms & " << model.callsToPredict << " & " << std::setprecision(3) << static_cast<double>(duration.count()) / static_cast<double>(model.callsToPredict) * 1000 << "us\\\\\n";

    planFile.close();
}
//---------------------------------------------------------------------------
void printPlanFeatures(Plan* p, bool printRoot) {
    if (!p->left) {
        assert(!p->right);
        return;
    }
    if (printRoot) {
        // std::cout << "Root:\n";
        p->openPipelineFeatures.print();
    }
    Features build = p->left->buildHashTable();
    // std::cout << "Build:\n";
    build.print();
    printPlanFeatures(p->left, false);
    printPlanFeatures(p->right, false);
}
//---------------------------------------------------------------------------
void inspectModel(QueryGraph q, Model& model) {
    q.prepareLookup();
    PlanGenerator<cost_model> pg;
    pg.model = &model;
    Plan* best = pg.runDPSize(q);
    std::cout << "cost of materialization pipelines " << best->matCost << "\n"
              << "overall cost " << best->cost << std::endl;
    std::cout << printPlan(best, q) << "\n";
    printPlanFeatures(best, true);
}

//---------------------------------------------------------------------------
Features sampleRandomFeatures(std::mt19937& gen) {
    std::uniform_real_distribution<> cardDis(0.0, 1000.0);
    std::uniform_real_distribution<> percentageDis(0.0, 1000.0);
    std::uniform_int_distribution<> discreteDis(0, 5);

    Features features{};
    features.TableScan_Scan_const = discreteDis(gen);
    features.TableScan_Scan_in_card = cardDis(gen);
    features.TableScan_Scan_out_percentage = percentageDis(gen);
    features.TableScan_Scan_empty_output = discreteDis(gen);

    features.HashJoin_Build_const = discreteDis(gen);
    features.HashJoin_Build_out_card = cardDis(gen);
    features.HashJoin_Build_out_size = discreteDis(gen);
    features.HashJoin_Build_in_percentage = percentageDis(gen);

    features.HashJoin_Probe_const = discreteDis(gen);
    features.HashJoin_Probe_in_card = cardDis(gen);
    features.HashJoin_Probe_right_percentage = percentageDis(gen);
    features.HashJoin_Probe_out_percentage = percentageDis(gen);

    return features;
}
//---------------------------------------------------------------------------
template <void (Model::*Func)()>
void benchmarkModelLatency(Model model) {
    std::random_device rd;
    std::mt19937 gen(rd());
    uint64_t nRuns = 10;
    // 3 pipelines per query is the observed average from our data set
    uint64_t nPipelinesPerQuery = 3;
    model.resetInput();
    for (uint64_t nQueries : {100000, 1}) {
        uint64_t nPipelines = nQueries * nPipelinesPerQuery;
        Model currentModel = model;
        currentModel.resize(nPipelines);
        std::vector<double> durations{};
        for (uint64_t i = 0; i < nRuns; ++i) {
            for (uint64_t f = 0; f < nPipelines; ++f) {
                currentModel.registerFeatures(sampleRandomFeatures(gen));
            }
            auto currentBegin = std::chrono::high_resolution_clock::now();
            // currentModel.predictManyCompiled();
            (currentModel.*Func)();
            auto currentEnd = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double, std::milli> duration = currentEnd - currentBegin;
            durations.push_back(duration.count());
        }
        double runTime = *std::min_element(durations.begin(), durations.end());
        std::cout << "Predicted " << nQueries << " Queries, time: "
                  << runTime << "ms, per query: " << runTime / static_cast<double>(nQueries) << "ms, throughput: "
                  << static_cast<double>(nQueries) / runTime * 1000 << "qps\n";
    }
}
//---------------------------------------------------------------------------
template <void (Model::*Func)()>
void benchmarkModelLatencyScaling(const Model& model, const std::string& outFilePath) {
    std::ofstream outFile(outFilePath);
    if (!outFile.is_open()) {
        return;
    }
    std::random_device rd;
    std::mt19937 gen(rd());
    uint64_t nRuns = 100;
    uint64_t limit = 1000;
    outFile << "{";
    for (uint64_t nPipelines = 1; nPipelines <= limit; ++nPipelines) {
        Model currentModel = model;
        currentModel.resize(nPipelines);
        std::vector<double> durations{};
        for (uint64_t i = 0; i < nRuns; ++i) {
            for (uint64_t f = 0; f < nPipelines; ++f) {
                currentModel.registerFeatures(sampleRandomFeatures(gen));
            }
            auto currentBegin = std::chrono::high_resolution_clock::now();
            // currentModel.predictManyCompiled();
            (currentModel.*Func)();
            auto currentEnd = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double, std::milli> duration =
                currentEnd - currentBegin;
            durations.push_back(duration.count());
        }
        double runTime = *std::min_element(durations.begin(), durations.end());
        outFile << "\"" << nPipelines << "\": " << runTime;
        if (nPipelines < limit)
            outFile << ", ";
    }
    outFile << "}\n";
    outFile.close();
}
//---------------------------------------------------------------------------
int main() {
    Model model;
    model.loadModel(fs::path("model.txt"));
    model.resize(1);
    model.prepare();

    benchmarkModelLatencyScaling<&Model::predictManyCompiled>(model, "./dp/latencyScalingCompiled.json");
    benchmarkModelLatencyScaling<&Model::predictMany>(model, "./dp/latencyScalingInterpretedMT.json");
    benchmarkModelLatencyScaling<&Model::predictManyST>(model, "./dp/latencyScalingInterpretedST.json");

    std::vector<QueryGraph> qs;
    std::vector<std::string> names;
    for (const auto& path : get_files()) {
        qs.push_back(parseDump(path));
        names.push_back(path.filename());
    }

    std::ofstream optTbl("./figure_output/tbl_join_order_speed.tex");
    optTbl << std::fixed;
    optTbl << "\\begin{tabular}{r|r r r}\n"
           << "Model & Opt. Time & Model Calls & Time/Call\\\\\n\\hline\n"
           << "$\\text{C}_{\\text{out}}$ & ";
    runModel<cost_cout>(fs::path("./dp/cout_plans.txt"), model, qs, names, optTbl);
    optTbl << "T3 & ";
    runModel<cost_model>(fs::path("./dp/model_plans.txt"), model, qs, names, optTbl);
    optTbl << "\\end{tabular}\n";
}
//---------------------------------------------------------------------------

#pragma clang diagnostic pop
