//
// RunAction.hh
//

#ifndef RunAction_h
#define RunAction_h 1

#include "G4UserRunAction.hh"
#include "globals.hh"
#include "G4Threading.hh"
#include "PhotonBuffer.hh"
#include "DoseBuffer.hh"
#include <string>
#include <fstream>
#include <chrono>
#include <sys/resource.h>

class G4Run;

class RunAction : public G4UserRunAction
{
  public:
    RunAction();              // 构造函数
    virtual ~RunAction();     // 虚析构函数，确保正确释放资源

    virtual void BeginOfRunAction(const G4Run*);  // 虚函数，要重写
    virtual void EndOfRunAction(const G4Run*);

    // 记录光子数据的函数，供 EventAction 调用
    void RecordPhotonData(G4double initX, G4double initY, G4double initZ,
                         G4double initDirX, G4double initDirY, G4double initDirZ,
                         G4double finalX, G4double finalY, G4double finalZ,
                         G4double finalDirX, G4double finalDirY, G4double finalDirZ,
                         G4double finalEnergy, G4int event_id, G4int track_id);

    void RecordDoseData(G4double x, G4double y, G4double z,
                        G4double dx, G4double dy, G4double dz,
                        G4double energy, G4int event_id, G4int pdg);

  private:
    // Output format: CSV or Binary
    std::string fOutputFormat;
    
    // For CSV output (thread-local files)
    static thread_local std::ofstream fThreadOutputStream;
    static std::string fOutputBasePath;
    
    // For Binary output (buffer-based)
    static thread_local PhotonBuffer* fThreadBuffer;
    static PhotonBuffer* fMasterBuffer;
    static thread_local DoseBuffer* fThreadDoseBuffer;
    static DoseBuffer* fMasterDoseBuffer;

    // Performance timing
    std::chrono::high_resolution_clock::time_point fStartTime;
    std::chrono::high_resolution_clock::time_point fEndTime;
    struct rusage fStartUsage;
    struct rusage fEndUsage;
    
    // Helper methods
    void WriteCSVHeader(std::ofstream& out);
    void MergeCSVThreadFiles();
    void WriteBinaryHeader(const std::string& headerPath);
    void WriteDoseHeader(const std::string& headerPath);
};

#endif
