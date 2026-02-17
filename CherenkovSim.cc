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


int main(int argc, char** argv)
{
  // ====================== 解析命令行参数 ======================
  // 支持: ./CherenkovSim [--config <config_file>] [macro_file]
  G4String configFilePath = "config.json";  // 默认配置文件名
  G4String macroFilePath = "";
  
  int argcForUI = 1;  // 为UI保留程序名
  char** argvForUI = new char*[argc];
  argvForUI[0] = argv[0];  // 保留程序名
  
  // 检查是否指定了config文件，并构建传给UI的清洁参数列表
  for (int i = 1; i < argc; i++) {
    G4String arg = argv[i];
    if (arg == "--config" || arg == "-c") {
      if (i + 1 < argc) {
        configFilePath = argv[++i];  // 获取下一个参数作为config文件路径
      }
    } else if (arg[0] != '-' && macroFilePath.empty()) {
      // 第一个非选项参数是macro文件
      macroFilePath = arg;
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
  if (argcForUI == 1) {
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
    G4String command = "/control/execute ";
    UImanager->ApplyCommand(command + macroFilePath);
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
