//
// ====================== Geant4 模拟基本流程 ======================
//
// 1. 创建 RunManager（核心控制器）
// 2. 注册几何（用户必须实现）
// 3. 注册物理列表（官方或自定义）
// 4. 注册用户行为（用户必须实现）
// 5. 初始化可视化（可选）
// 6. 执行宏文件或启动交互
// 7. 程序结束释放资源
//
// ==================================================================
//

#include "DetectorConstruction.hh"   // 【用户自定义】继承 G4VUserDetectorConstruction
#include "ActionInitialization.hh"   // 【用户自定义】继承 G4VUserActionInitialization
#include "Config.hh"                 // 【配置文件】读取模拟参数

#include "G4RunManagerFactory.hh"    // 【GEANT4 内核】创建 RunManager
#include "G4UImanager.hh"            // 【GEANT4 内核】命令接口
#include "G4VisExecutive.hh"         // 【GEANT4 内核】可视化管理器
#include "G4UIExecutive.hh"          // 【GEANT4 内核】交互界面
#include "FTFP_BERT.hh"              // 【可选模块】官方强子物理
#include "G4EmStandardPhysics_option4.hh" // 【可选模块】高精度电磁物理
#include "G4OpticalPhysics.hh"       // 【可选模块】光学物理（Cherenkov）
#include "G4SystemOfUnits.hh"        // 【GEANT4 内核】单位系统
#include "Randomize.hh"              // 【GEANT4 内核】随机数工具

// 运行模式：用于集中控制 test / full / custom 等
struct RunModeConfig {
  enum class Mode {
    None,
    Test,
    Full,
    Custom
  };

  Mode     mode = Mode::None;
  G4int    events = 0;           // 若 >0，则用于 /run/beamOn 的事件数
  G4String macroFilePath = "";   // 要执行的基础宏（推荐不含 beamOn）
};

int main(int argc, char** argv)
{
  // ====================== 解析命令行参数 ======================
  // 支持:
  //   ./CherenkovSim [--config <config_file>] [macro_file]
  //   ./CherenkovSim --config <cfg> --mode test|full|custom [--events N] [--macro file.mac]
  G4String configFilePath = "config.json";  // 默认配置文件名
  RunModeConfig runCfg;

  int argcForUI = 1;  // 为UI保留程序名
  char** argvForUI = new char*[argc];
  argvForUI[0] = argv[0];  // 保留程序名

  // 检查是否指定了config文件、运行模式以及宏文件
  for (int i = 1; i < argc; i++) {
    G4String arg = argv[i];
    if (arg == "--config" || arg == "-c") {
      if (i + 1 < argc) {
        configFilePath = argv[++i];  // 获取下一个参数作为config文件路径
      }
    } else if (arg == "--mode") {
      if (i + 1 < argc) {
        G4String m = argv[++i];
        if (m == "test") {
          runCfg.mode = RunModeConfig::Mode::Test;
        } else if (m == "full") {
          runCfg.mode = RunModeConfig::Mode::Full;
        } else if (m == "custom") {
          runCfg.mode = RunModeConfig::Mode::Custom;
        } else {
          G4cerr << "Unknown mode: " << m << G4endl;
        }
      }
    } else if (arg == "--events") {
      if (i + 1 < argc) {
        runCfg.events = std::atoi(argv[++i]);
      }
    } else if (arg == "--macro") {
      if (i + 1 < argc) {
        runCfg.macroFilePath = argv[++i];
        argvForUI[argcForUI++] = argv[i];  // 只传递macro文件给UI
      }
    } else if (arg[0] != '-' && runCfg.macroFilePath.empty()) {
      // 兼容旧用法：第一个非选项参数是macro文件
      runCfg.macroFilePath = arg;
      argvForUI[argcForUI++] = argv[i];  // 只传递macro文件给UI
    }
  }

  // 【注意】随机数种子通过 MAC 文件设置：/random/setSeeds seed1 seed2
  // 源码不再硬编码种子，以便用户灵活配置

  // ====================== 加载配置文件 ======================
  // 【配置文件】从 JSON 文件加载所有参数
  Config* config = Config::GetInstance();
  config->LoadConfig(configFilePath);

  // ====================== 运行模式判断 ======================
  // 【程序流程】是否进入交互模式
  G4UIExecutive* ui = nullptr;
  if (argcForUI == 1 && runCfg.macroFilePath.empty()) {
    // 交互模式：没有指定macro文件
    ui = new G4UIExecutive(argcForUI, argvForUI);  // 【GEANT4 内核】
  }

  // ====================== 创建核心控制器 ======================
  // 【GEANT4 内核】整个模拟的"大脑"
  auto* runManager = G4RunManagerFactory::CreateRunManager();

  runManager->SetNumberOfThreads(config->GetNumThreads());  // 【配置文件】从配置读取线程数

  // ====================== 注册几何 ======================
  // 【用户自定义】你必须实现 Construct()
  runManager->SetUserInitialization(new DetectorConstruction());

  // ====================== 注册物理 ======================
  // 【GEANT4 内核,可选】使用官方物理列表
  G4VModularPhysicsList* physicsList = new FTFP_BERT;

  // 【GEANT4 内核,可选】替换电磁模型
  physicsList->ReplacePhysics(new G4EmStandardPhysics_option4());
  
  // 【GEANT4 内核,可选】注册光学过程（Cherenkov 在这里产生）
  G4OpticalPhysics* opticalPhysics = new G4OpticalPhysics();
  physicsList->RegisterPhysics(opticalPhysics);

  // 【GEANT4 内核】把物理列表交给 RunManager
  runManager->SetUserInitialization(physicsList);

  // ====================== 注册用户行为 ======================
  // 【用户自定义】内部创建：
  //   PrimaryGeneratorAction
  //   RunAction
  //   EventAction
  //   SteppingAction
  runManager->SetUserInitialization(new ActionInitialization());

  // ====================== 可视化初始化 ======================
  // 【GEANT4 内核】可选模块
  G4VisManager* visManager = new G4VisExecutive;
  visManager->Initialize();

  // ====================== 获取命令管理器 ======================
  // 【GEANT4 内核】单例模式
  G4UImanager* UImanager = G4UImanager::GetUIpointer();

  // ====================== 执行阶段 ======================
  if (!ui) {
    // 【程序流程】Batch 模式
    if (!runCfg.macroFilePath.empty()) {
      G4String command = "/control/execute ";
      UImanager->ApplyCommand(command + runCfg.macroFilePath);
    }

    // 若指定了运行模式，并且事件数已确定，则在基础宏之后统一发出 /run/beamOn
    if (runCfg.mode != RunModeConfig::Mode::None) {
      G4int beamOnEvents = 0;
      if (runCfg.mode == RunModeConfig::Mode::Test) {
        // Test 模式默认 100 事件，若用户通过 --events 指定则覆盖
        beamOnEvents = (runCfg.events > 0) ? runCfg.events : 100;
      } else if (runCfg.mode == RunModeConfig::Mode::Full) {
        // Full 模式默认使用完整 PHSP 事件数（52,302,569），可被 --events 覆盖
        beamOnEvents = (runCfg.events > 0) ? runCfg.events : 52302569;
      } else if (runCfg.mode == RunModeConfig::Mode::Custom) {
        // Custom 模式必须显式指定事件数
        if (runCfg.events <= 0) {
          G4cerr << "Custom mode requires --events <N>" << G4endl;
        } else {
          beamOnEvents = runCfg.events;
        }
      }

      if (beamOnEvents > 0) {
        G4String beamOnCmd = "/run/beamOn " + std::to_string(beamOnEvents);
        UImanager->ApplyCommand(beamOnCmd);
      }
    }
  }
  else {
    // 【程序流程】Interactive 模式
    UImanager->ApplyCommand("/control/execute init_vis.mac");
    ui->SessionStart();
    delete ui;
  }

  // ====================== 程序结束 ======================
  // 【GEANT4 内核】释放资源
  delete visManager;
  delete runManager;
  delete[] argvForUI;

  return 0;
}
